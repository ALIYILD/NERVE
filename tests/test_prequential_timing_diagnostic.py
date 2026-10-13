"""Read-only tests against recorded development receipts; never run episodes."""
from copy import deepcopy
import gzip
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.memory_gateway import prequential_timing_diagnostic as subject

ARTIFACT = subject.demo.standard.ROOT/'docs/galahad/evidence/prequential-gain-development-v1.json.gz'


class PrequentialTimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.raw,cls.report = subject._read(ARTIFACT)

    def test_full_verified_receipt_never_runs_new_episodes(self):
        with patch.object(subject.demo,'execute',side_effect=AssertionError('no episodes')), patch.object(subject.demo,'run_demo',side_effect=AssertionError('no episodes')):
            result=subject.run(ARTIFACT)
        self.assertEqual(len(result['source_sha256']),25)
        self.assertEqual(result['new_episodes'],0)
        self.assertFalse(result['promotion_authorized'])
        self.assertEqual(len(result['cases']),4)

    def test_eligibility_is_not_nonzero_actuation(self):
        result=subject.analyze(self.report)
        lower=next(case for case in result['cases'] if case['plant']=='lower')
        self.assertGreater(lower['summary']['eligible'],0)
        self.assertEqual(lower['summary']['eligible_nonzero_command'],0)
        for case in result['cases']:
            summary=case['summary']
            self.assertEqual(summary['eligible_controller_command']+summary['eligible_external_step'],summary['eligible'])
            self.assertLessEqual(summary['eligible_nonzero_command'],summary['eligible_controller_command'])

    def test_each_resolved_forecast_scored_once_with_delays(self):
        result=subject.analyze(self.report)
        for case in result['cases']:
            source=next(row for row in self.report['rows'] if row['plant']==case['plant'] and row['arm']=='selector')
            scores=[score for step in case['steps'] for score in step['new_scores']]
            self.assertEqual(len(scores),len({score['forecast_step'] for score in scores}))
            self.assertEqual(len(scores),source['trace'][-1]['selector_after']['counts']['resolved'])
            for score in scores:
                self.assertGreater(score['delay_steps'],0)
                self.assertEqual(score['delay_steps'],score['resolved_step']-score['forecast_step'])
                delta=score['learned_error']-score['nominal_error']
                self.assertEqual(score['outcome'],'win' if delta<0 else 'loss' if delta>0 else 'tie')

    def test_intervals_and_switches_match_exact_snapshot_modes(self):
        for case in subject.analyze(self.report)['cases']:
            eligible={step['step'] for step in case['steps'] if step['eligible']}
            intervals={step for interval in case['eligibility_intervals'] for step in range(interval['start'],interval['end_exclusive'])}
            self.assertEqual(intervals,eligible)
            for switch in case['switches']:
                previous=[r for r in case['authorized_recovery_steps'] if r<=switch['step']]
                self.assertEqual(switch['steps_since_authorized_recovery'],switch['step']-previous[-1] if previous else None)
            full=[step['step'] for step in case['steps'] if step['window_size']==4]
            self.assertEqual(case['first_full_window_step'],full[0] if full else None)

    def test_phase_partition_and_rejection_reasons_are_complete(self):
        for case in subject.analyze(self.report)['cases']:
            self.assertEqual(sum(phase['steps'] for phase in case['phases']),80)
            self.assertEqual(sum(case['summary']['window_reasons'].values()),80)
            for phase in case['phases']:
                self.assertEqual(phase['steps'],20)
                self.assertEqual(phase['start'],20*phase['phase'])
            for key in case['summary']['resolved_outcomes']:
                self.assertEqual(sum(phase['resolved_outcomes'][key] for phase in case['phases']),case['summary']['resolved_outcomes'][key])

    def test_roster_metadata_source_and_screen_tampering_rejected(self):
        for change in ('missing','duplicate','seed','pins','rowpins','screen','flag','recommendation'):
            report=deepcopy(self.report)
            if change=='missing':report['rows'].pop()
            if change=='duplicate':report['rows'][1]=deepcopy(report['rows'][0])
            if change=='seed':report['rows'][0]['seed']=10
            if change=='pins':report['source_sha256']={}
            if change=='rowpins':report['rows'][0]['source_sha256']={}
            if change=='screen':report['screen']['passed']=True
            if change=='flag':report['candidate_promoted']=0
            if change=='recommendation':report['recommendation']='register_fresh_study'
            with self.subTest(change=change), self.assertRaises(ValueError):subject.validate(report)

    def test_physical_learning_and_selector_tampering_rejected(self):
        for change in ('truth','learning','selector','action'):
            report=deepcopy(self.report); row=report['rows'][2]
            if change=='truth':row['trace'][10]['true_velocity']+=.1
            if change=='learning':row['learning_audit']['ema_applications']+=1
            if change=='selector':row['trace'][10]['selector_before']['mode']='learned'
            if change=='action':row['trace'][10]['action']=True
            with self.subTest(change=change),self.assertRaises(ValueError):subject.validate(report)

    def test_artifact_and_code_changes_are_detected(self):
        with patch.object(subject,'_read',side_effect=[(self.raw,self.report),(self.raw+b'x',self.report)]):
            with self.assertRaisesRegex(ValueError,'artifact_changed'):subject.load_verified(ARTIFACT)
        with patch.object(subject,'sources',side_effect=[{'a':1},{'a':2}]):
            with self.assertRaisesRegex(ValueError,'source_code_changed'):subject.load_verified(ARTIFACT)
        verified=subject.load_verified(ARTIFACT)
        with patch.object(subject,'load_verified',return_value=verified),patch.object(subject,'_read',return_value=(self.raw+b'x',self.report)):
            with self.assertRaisesRegex(ValueError,'artifact_changed'):subject.run(ARTIFACT)

    def test_bounds_duplicate_json_and_nonfinite_json_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'data.gz'
            for payload in (b'{"a":1,"a":2}',b'{"a":NaN}'):
                path.write_bytes(gzip.compress(payload))
                with self.assertRaises(ValueError):subject._read(path)
            path.write_bytes(gzip.compress(b' '*100))
            with patch.object(subject,'MAX_EXPANDED',20),self.assertRaises(ValueError):subject._read(path)
            with patch.object(subject,'MAX_COMPRESSED',1),self.assertRaises(ValueError):subject._read(path)

    def test_analysis_does_not_mutate_source_evidence(self):
        before=deepcopy(self.report)
        subject.analyze(self.report)
        self.assertEqual(self.report,before)


if __name__=='__main__':unittest.main()
