"""Durable content/family reservations reject relabeling and downgrade paths."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest

import test_cue_learning as fixtures
from nerve_awim.cue_dataset import parse_dataset_json
from nerve_awim.cue_evaluation import DatasetManifest
from nerve_awim.cue_learning import GovernedCueCoordinator


class CueDatasetReservationTests(unittest.TestCase):
    setUp = fixtures.CueLearningTests.setUp

    def record(self, suffix=''):
        return {'schema_version':1,'dataset_id':'dataset'+suffix,
            'source':{'uri':'fixture:source'+suffix,'revision':'v1'},
            'splits':{split:[{'task_id':split+str(i)+suffix,'family_id':split+'family'+suffix,
                'instruction':split+' question '+str(i)+suffix,'expected':'answer'}
                for i in range(2 if split=='holdout' else 1)]
                for split in ('discovery','selection','holdout')}}

    def dataset(self, record=None):
        return parse_dataset_json(json.dumps(self.record() if record is None else record))

    def reserve(self, record=None, actor=None):
        return self.cce.reserve_dataset(actor or self.actors['trainer'],self.dataset(record))

    def counts(self):
        with self.engine._db() as con:
            return {table:con.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]
                for table in ('cce_studies','cce_partitions','cce_dataset_studies',
                              'cce_dataset_fingerprints','cce_versions','cce_candidates','gl_events')}

    def test_renamed_ids_source_family_answers_cannot_recycle_holdout(self):
        self.reserve()
        relabeled=self.record('-renamed')
        relabeled['source']={'uri':'another:publisher','revision':'different'}
        for old,new in zip(self.record()['splits']['holdout'],relabeled['splits']['holdout']):
            new['instruction']='  '+old['instruction']+'\n'
            new['expected']='changed-answer'
        before=self.counts()
        with self.assertRaisesRegex(ValueError,'content/family'):
            self.reserve(relabeled)
        self.assertEqual(before,self.counts())

    def test_holdout_family_with_new_content_is_burned(self):
        self.reserve()
        record=self.record('-fresh')
        for task in record['splits']['holdout']:
            task['family_id']='holdoutfamily'
        with self.assertRaisesRegex(ValueError,'content/family'):
            self.reserve(record)

    def test_discovery_selection_reuse_allowed_only_same_split(self):
        self.reserve()
        record=self.record('-fresh')
        for split in ('discovery','selection'):
            record['splits'][split]=deepcopy(self.record()['splits'][split])
        self.reserve(record)
        self.assertEqual(self.counts()['cce_dataset_studies'],2)
        # Two holdout tasks share a family inside each reservation legitimately.
        self.assertEqual(self.counts()['cce_dataset_fingerprints'],10)

    def test_all_cross_split_moves_fail_despite_renamed_ids(self):
        self.reserve()
        for source in ('discovery','selection','holdout'):
            for destination in ('discovery','selection','holdout'):
                if source==destination: continue
                record=self.record('-'+source+'-'+destination)
                record['splits'][destination][0]['instruction']=self.record()['splits'][source][0]['instruction']
                with self.subTest(source=source,destination=destination), self.assertRaises(ValueError):
                    self.reserve(record)

    def test_id_conflict_after_content_preflight_rolls_back_every_table(self):
        self.reserve()
        record=self.record('-fresh')
        record['splits']['holdout'][0]['task_id']='holdout0'
        before=self.counts()
        with self.assertRaisesRegex(ValueError,'holdout'):
            self.reserve(record)
        self.assertEqual(self.counts(),before)
        # The fresh content/family from the aborted attempt was not burned.
        record['splits']['holdout'][0]['task_id']='fixedholdout'
        self.reserve(record)

    def test_reservations_survive_coordinator_restart(self):
        self.reserve()
        self.cce=GovernedCueCoordinator(self.engine,enabled=True,clock=lambda:self.now)
        with self.assertRaises(ValueError): self.reserve()
        with self.assertRaisesRegex(ValueError,'downgrade'):
            self.cce.reserve_study(self.actors['trainer'],DatasetManifest(('newd',),('news',),('newh',)))

    def test_legacy_reservation_and_implicit_proposal_cannot_downgrade(self):
        legacy=DatasetManifest(('legacyd',),('legacys',),('legacyh',))
        old=self.cce.reserve_study(self.actors['trainer'],legacy)
        self.reserve()
        before=self.counts()
        with self.assertRaisesRegex(ValueError,'dataset'):
            self.cce.propose(self.actors['trainer'],self.cue,self.profile,'research',legacy,
                generator_id='generator',model_config=self.model,reservation=old)
        self.assertEqual(before,self.counts())
        with self.assertRaisesRegex(ValueError,'downgrade'):
            self.cce.propose(self.actors['trainer'],self.cue,self.profile,'research',legacy,
                generator_id='generator',model_config=self.model)
        self.assertEqual(before,self.counts())

    def test_dataset_reservation_consumes_once_and_links_candidate(self):
        dataset=self.dataset()
        reservation=self.cce.reserve_dataset(self.actors['trainer'],dataset)
        candidate=self.cce.propose(self.actors['trainer'],self.cue,self.profile,'research',dataset.manifest,
            generator_id='generator',model_config=self.model,reservation=reservation)
        with self.engine._db() as con:
            row=con.execute('SELECT candidate FROM cce_dataset_studies WHERE reservation=?',(reservation,)).fetchone()
            self.assertEqual(row['candidate'],candidate)
        with self.assertRaises(ValueError):
            self.cce.propose(self.actors['trainer'],replace(self.cue,version=2),self.profile,'research',dataset.manifest,
                generator_id='generator',model_config=self.model,reservation=reservation)

    def test_scope_isolation_and_role_validation(self):
        self.reserve()
        for tenant,agent in (('tenant','other'),('other','agent')):
            operator=self.authority.issue(tenant,agent,'operator')
            trainer=self.authority.issue(tenant,agent,'trainer')
            self.engine.bootstrap(operator)
            self.reserve(actor=trainer)
        self.assertEqual(self.counts()['cce_dataset_studies'],3)
        with self.assertRaises(PermissionError):self.reserve(actor=self.actors['runtime'])

    def legacy_candidate(self, *, evaluate=False, activate=False):
        candidate = self.cce.propose(self.actors['trainer'],self.cue,self.profile,'research',self.manifest,
            generator_id='generator',model_config=self.model)
        if evaluate:
            outcome = self.cce.evaluate(self.actors['evaluator'],candidate,
                fixtures.CueLearningTests.pairs(self),evaluator_id='independent')
            self.assertTrue(outcome['decision']['eligible'])
        if activate:
            self.cce.activate(self.actors['operator'],candidate,expected_generation=0,reason='legacy-review')
            self.assertIsNotNone(self.cce.select(self.actors['runtime'],self.profile,'research',permission_granted=True).cue)
        return candidate

    def test_legacy_pending_evaluation_denied_after_dataset_cutover(self):
        candidate = self.legacy_candidate()
        self.reserve()
        with self.assertRaises((ValueError, PermissionError)):
            self.cce.evaluate(self.actors['evaluator'],candidate,
                fixtures.CueLearningTests.pairs(self),evaluator_id='independent')
        self.assertEqual(self.cce.status(self.actors['auditor'],candidate)['status'],'pending')

    def test_legacy_passed_activation_denied_after_dataset_cutover(self):
        candidate = self.legacy_candidate(evaluate=True)
        self.reserve()
        with self.assertRaises((ValueError, PermissionError)):
            self.cce.activate(self.actors['operator'],candidate,expected_generation=0,reason='review')
        self.assertEqual(self.cce.status(self.actors['auditor'],candidate)['status'],'passed')

    def test_legacy_active_route_falls_back_without_erasing_audit_after_cutover(self):
        candidate = self.legacy_candidate(evaluate=True,activate=True)
        before = self.counts()['gl_events']
        self.reserve()
        self.assertIsNone(self.cce.select(self.actors['runtime'],self.profile,'research',permission_granted=True).cue)
        self.assertEqual(self.cce.status(self.actors['auditor'],candidate)['status'],'approved')
        self.assertGreater(self.counts()['gl_events'],before)
        self.cce = GovernedCueCoordinator(self.engine,enabled=True,clock=lambda:self.now)
        self.assertIsNone(self.cce.select(self.actors['runtime'],self.profile,'research',permission_granted=True).cue)

    def test_forged_frozen_dataset_rejected_before_writes(self):
        dataset=self.dataset()
        before=self.counts()
        for forged in (replace(dataset,digest='f'*64),replace(dataset,families=()),
                       replace(dataset,holdout_tasks=dataset.holdout_tasks[:1])):
            with self.assertRaises(ValueError):
                self.cce.reserve_dataset(self.actors['trainer'],forged)
        self.assertEqual(self.counts(),before)


if __name__=='__main__':unittest.main()
