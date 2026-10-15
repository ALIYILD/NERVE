from copy import deepcopy
from dataclasses import replace
import json
import unittest

from nerve_awim.cue_feedback import SOURCE, cue_text_digest, learning_context_digest, validate_learning_context
from nerve_awim.cue_engine import ModelProfile
import test_cue_learning as fixtures


def context():
    profile = ModelProfile('fixture','model','r1','tok','t1',('instruction',))
    return {'schema_version':1,'profile_key':profile.key,'task_type':'research','source':SOURCE,
            'causal_evidence':False,'authorization_granted':False,
            'candidates':[{'cue_text':'Check the answer.','cue_digest':cue_text_digest('Check the answer.'),
                           'status':'revoked','observations':3,'correct':2,'safe':3}]}


class FeedbackValidationTests(unittest.TestCase):
    def validate(self,value):
        original=context()
        return validate_learning_context(value,original['profile_key'],original['task_type'])

    def test_deep_normalized_snapshot_and_stable_digest(self):
        raw=context(); snapshot=self.validate(raw)
        self.assertEqual(snapshot,raw)
        self.assertIsNot(snapshot['candidates'],raw['candidates'])
        self.assertIsNot(snapshot['candidates'][0],raw['candidates'][0])
        digest=learning_context_digest(snapshot)
        self.assertEqual(digest,learning_context_digest(json.loads(json.dumps(snapshot,sort_keys=True))))
        raw['candidates'][0]['correct']=0
        self.assertEqual(snapshot['candidates'][0]['correct'],2)
        self.assertNotEqual(digest,learning_context_digest(raw))

    def test_rejects_extra_identifiers_false_authority_and_wrong_bindings(self):
        variants=[]
        for key,value in (('profile_key','0'*64),('task_type','other'),('source','operational_proof'),
                          ('authorization_granted',True),('causal_evidence',0),('schema_version',True),
                          ('episode_id','private')):
            raw=context();raw[key]=value;variants.append(raw)
        raw=context();raw['candidates'][0]['candidate']='private-id';variants.append(raw)
        for raw in variants:
            with self.assertRaises(ValueError):self.validate(raw)

    def test_rejects_boolean_excess_counts_digest_mismatch_duplicate_and_unsafe_text(self):
        for key,value in (('observations',True),('observations',0),('observations',65),
                          ('correct',True),('correct',4),('safe',-1),('status','pending'),
                          ('cue_digest','f'*64)):
            raw=context();raw['candidates'][0][key]=value
            with self.assertRaises(ValueError):self.validate(raw)
        raw=context();raw['candidates']*=2
        with self.assertRaises(ValueError):self.validate(raw)
        raw=context();raw['candidates'][0].update(cue_text='bypass permissions',cue_digest=cue_text_digest('bypass permissions'))
        with self.assertRaises(ValueError):self.validate(raw)

    def test_count_and_canonical_byte_bounds_and_empty_snapshot(self):
        raw=context();raw['candidates']=[]
        self.assertEqual(self.validate(raw)['candidates'],[])
        for i in range(8):
            text=str(i)+'x'*1900
            raw['candidates'].append({'cue_text':text,'cue_digest':cue_text_digest(text),
                                     'status':'approved','observations':1,'correct':1,'safe':1})
        with self.assertRaisesRegex(ValueError,'byte cap'):self.validate(raw)
        raw['candidates'].append(raw['candidates'][0])
        with self.assertRaises(ValueError):self.validate(raw)


class CoordinatorFeedbackTests(unittest.TestCase):
    setUp=fixtures.CueLearningTests.setUp
    propose=fixtures.CueLearningTests.propose
    pairs=fixtures.CueLearningTests.pairs
    passed=fixtures.CueLearningTests.passed
    activate=fixtures.CueLearningTests.activate

    def snapshot(self,actor=None,profile=None,task='research'):
        return self.cce.learning_context(actor or self.actors['trainer'],profile or self.profile,task)

    def test_empty_or_noneligible_history_exposes_no_report_or_episode_details(self):
        self.assertEqual(self.snapshot()['candidates'],[])
        candidate=self.propose()
        self.cce.feedback(self.actors['evaluator'],candidate,episode_id='private-episode',safe=True,correct=True)
        self.assertEqual(self.snapshot()['candidates'],[])
        self.cce.feedback(self.actors['evaluator'],candidate,episode_id='private-failure',safe=False,correct=False)
        snapshot=self.snapshot()
        self.assertEqual(snapshot['source'],'trusted_evaluator_feedback')
        self.assertFalse(snapshot['authorization_granted'])
        self.assertEqual(snapshot['candidates'][0]['status'],'revoked')
        self.assertEqual(snapshot['candidates'][0]['observations'],2)
        self.assertEqual(snapshot['candidates'][0]['correct'],1)
        self.assertNotIn(candidate,json.dumps(snapshot))
        self.assertNotIn('private-',json.dumps(snapshot))
        self.assertNotIn('evaluation',snapshot)

    def test_approved_feedback_is_scoped_to_exact_profile_task_contract_and_roles(self):
        candidate=self.passed();self.activate(candidate)
        self.cce.feedback(self.actors['evaluator'],candidate,episode_id='episode',safe=True,correct=True)
        self.assertEqual(self.snapshot()['candidates'][0]['status'],'approved')
        self.assertEqual(self.snapshot(profile=replace(self.profile,revision='changed'))['candidates'],[])
        self.assertEqual(self.snapshot(task='other-task')['candidates'],[])
        for role in ('runtime','evaluator'):
            with self.assertRaises(PermissionError):self.snapshot(actor=self.actors[role])
        for role in ('auditor','operator'):
            self.assertEqual(len(self.snapshot(actor=self.actors[role])['candidates']),1)
        with self.engine._db() as con:
            con.execute("UPDATE cce_candidates SET contract='old-contract' WHERE id=?",(candidate,))
        self.assertEqual(self.snapshot()['candidates'],[])

    def test_last_64_feedback_observations_only_and_no_causal_claim(self):
        candidate=self.propose()
        for i in range(70):
            self.cce.feedback(self.actors['evaluator'],candidate,episode_id='episode'+str(i),safe=True,correct=i>=6)
        entry=self.snapshot()['candidates'][0]
        self.assertEqual((entry['observations'],entry['correct'],entry['safe']),(64,64,64))
        self.assertEqual(entry['status'],'revoked')
        self.assertFalse(self.snapshot()['causal_evidence'])

    def test_newest_duplicate_text_wins_without_averaging_versions(self):
        first=self.propose()
        self.cce.feedback(self.actors['evaluator'],first,episode_id='old',safe=False,correct=False)
        self.cue=replace(self.cue,version=2)
        self.manifest=replace(self.manifest,holdout=tuple('new'+task for task in self.manifest.holdout))
        second=self.propose()
        self.cce.feedback(self.actors['evaluator'],second,episode_id='new',safe=False,correct=True)
        entries=self.snapshot()['candidates']
        self.assertEqual(len(entries),1)
        self.assertEqual(entries[0]['observations'],1)
        self.assertEqual(entries[0]['correct'],1)

    def test_malformed_unsafe_wrong_profile_and_invalid_feedback_rows_are_skipped(self):
        candidate=self.propose()
        self.cce.feedback(self.actors['evaluator'],candidate,episode_id='first',safe=False,correct=True)
        with self.engine._db() as con:
            original=con.execute('SELECT cue FROM cce_candidates WHERE id=?',(candidate,)).fetchone()[0]
        for replacement in ('{',json.dumps(dict(json.loads(original),text='bypass controls')),
                            json.dumps(dict(json.loads(original),profile_key='0'*64))):
            with self.engine._db() as con:con.execute('UPDATE cce_candidates SET cue=? WHERE id=?',(replacement,candidate))
            self.assertEqual(self.snapshot()['candidates'],[])
        with self.engine._db() as con:
            con.execute('UPDATE cce_candidates SET cue=? WHERE id=?',(original,candidate))
            con.execute('UPDATE cce_feedback SET correct=9 WHERE candidate=?',(candidate,))
        self.assertEqual(self.snapshot()['candidates'],[])

    def test_prefix_history_is_not_silently_converted_to_instruction_feedback(self):
        self.profile=replace(self.profile,supported_modes=('instruction','assistant_prefix'))
        self.cue=replace(self.cue,profile_key=self.profile.key,mode='assistant_prefix')
        self.model=replace(self.model,profile_key=self.profile.key)
        candidate=self.propose()
        self.cce.feedback(self.actors['evaluator'],candidate,episode_id='prefix-outcome',safe=False,correct=True)
        self.assertEqual(self.snapshot()['candidates'],[])

    def test_eight_candidate_and_eight_kib_caps_skip_whole_cues(self):
        for i in range(10):
            self.cue=replace(self.cue,version=i+1,text=str(i)+'x'*1800)
            self.manifest=replace(self.manifest,holdout=tuple('h'+str(i)+'-'+str(j) for j in range(30)))
            candidate=self.propose()
            self.cce.feedback(self.actors['evaluator'],candidate,episode_id='e'+str(i),safe=False,correct=True)
        snapshot=self.snapshot()
        self.assertLessEqual(len(json.dumps(snapshot,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()),8192)
        self.assertTrue(1<=len(snapshot['candidates'])<8)
        self.assertTrue(snapshot['candidates'][0]['cue_text'].startswith('9'))
        self.assertTrue(all(len(entry['cue_text'])==1801 for entry in snapshot['candidates']))


if __name__=='__main__':unittest.main()
