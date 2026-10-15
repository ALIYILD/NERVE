"""Format failures are learning feedback only in the training partition."""
import copy
import json
import unittest

import test_agentos_cohort_study as fixtures

runner=fixtures.runner
oracle=fixtures.oracle


class TrainingFailureTests(unittest.TestCase):
    setUp=fixtures.CohortStudyTests.setUp
    fake=fixtures.CohortStudyTests.fake

    def malformed(self,phase='train',mode='citation'):
        base=self.fake()
        entry=fixtures.registry.get(self.host,self.entry['id'])
        ids={r['id'] for r in entry['data']['splits'][phase]}
        def native(*args,**kw):
            receipt=base(*args,**kw)
            if kw.get('inspect') or set(receipt['value'])!=ids:
                return receipt
            payload=json.loads(args[2].rsplit('\n',1)[-1])
            if mode=='batch':
                receipt['value']={}
            elif mode=='oversize':
                receipt['value'][next(iter(ids))]='x'*65537
            else:
                for task in payload['tasks']:
                    # Actual live failure shape: source record copied as citation.
                    receipt['value'][task['id']]={'decision':'supported','citations':[copy.deepcopy(task['bundle']['sources'][0])]}
            return receipt
        return native,entry

    def test_invalid_training_reaches_proposer_and_history_as_errors(self):
        native,entry=self.malformed()
        result=runner.run(self.host,native,self.entry)
        self.assertEqual(result['status'],'shadow_accepted')
        feedback=json.loads(self.prompts[1].rsplit('\n',1)[-1])
        self.assertEqual(len(feedback),len(entry['data']['splits']['train']))
        for row in feedback:
            self.assertEqual(row['feedback']['category'],'invalid_output')
            self.assertFalse(row['feedback']['passed'])
            self.assertIn('id',row['answer']['citations'][0])
        runner.candidate(self.host,result['study_id'])
        history=runner.learning_history(self.host,entry['profile'],'test:free',runner.current_revision(),entry['data']['scope'])
        self.assertEqual(len(history['lessons']),1)
        self.assertEqual(history['lessons'][0]['train_hits'],0)
        self.assertEqual(history['lessons'][0]['train_errors'],len(feedback))
        self.assertEqual(result['native_sessions'],8)
        self.assertFalse(result['activation_authorized'])

    def test_all_heldout_phases_reject_same_malformed_citations(self):
        for phase in ('selection','retention','final'):
            with self.subTest(phase=phase):
                # Separate isolated ledgers/cohorts for each experiment.
                self.setUp()
                native,_=self.malformed(phase)
                result=runner.run(self.host,native,self.entry)
                self.assertEqual(result['status'],'failed')
                self.assertEqual(result['reason'],'ValueError')
                with self.assertRaises(ValueError):
                    runner.candidate(self.host,result['study_id'])

    def test_training_batch_shape_and_size_remain_strict(self):
        for mode in ('batch','oversize'):
            with self.subTest(mode=mode):
                self.setUp()
                native,_=self.malformed(mode=mode)
                result=runner.run(self.host,native,self.entry)
                self.assertEqual(result['status'],'failed')
                self.assertEqual(result['native_sessions'],1)
                self.assertEqual(len(self.prompts),1)


if __name__=='__main__':
    unittest.main()
