"""Review a fixed protocol only before any study consumes the frozen cohort."""
from contextlib import redirect_stdout
import io
import json
import sqlite3
import sys
import unittest
from unittest.mock import Mock, patch

import test_agentos_cohort_study as fixtures
import agentos_bridge as bridge

runner=fixtures.runner


class QueueReviewTests(unittest.TestCase):
    setUp=fixtures.CohortStudyTests.setUp
    fake=fixtures.CohortStudyTests.fake

    def queued(self):
        native=Mock(side_effect=AssertionError('no inference while queued'))
        with patch.object(runner,'current_revision',return_value='a'*64),patch.object(runner,'remaining',return_value=0):
            self.assertEqual(runner.run(self.host,native,self.entry)['status'],'queued_budget')
        self.assertEqual(runner.run(self.host,native,self.entry)['status'],'queued_revision_mismatch')
        native.assert_not_called()
        return dict(cohort=self.entry['id'],previous_revision='a'*64,revision=runner.current_revision(),
                    manifest_sha256=self.entry['manifest_sha256'],reviewer='independent test operator',
                    reason='Reviewed output contract fix; same unexposed dataset and evaluator.')

    def test_explicit_review_preserves_original_pin_budget_and_once_only_execution(self):
        review=self.queued()
        remaining=runner.remaining(self.host)
        result=runner.review_queue(self.host,review)
        self.assertEqual(result['provider_calls'],0)
        self.assertFalse(result['activation_authorized'])
        self.assertEqual(runner.remaining(self.host),remaining)
        with sqlite3.connect(runner.database(self.host)) as db:
            self.assertEqual(db.execute('SELECT revision FROM queued').fetchone()[0],'a'*64)
            self.assertEqual(runner.reviewed_queue(db,self.entry['id']),(review['revision'],review['manifest_sha256']))
        result=runner.run(self.host,self.fake(),self.entry)
        self.assertEqual(result['status'],'shadow_accepted')
        self.assertEqual(runner.remaining(self.host),12)
        runner.candidate(self.host,result['study_id'])
        with self.assertRaises(ValueError):
            runner.review_queue(self.host,review)
        self.assertEqual(runner.run(self.host,self.fake(),self.entry)['status'],'no_fresh_tasks')
        self.assertEqual(runner.remaining(self.host),12)

    def test_stale_source_manifest_unqueued_and_extra_fields_fail_closed(self):
        review=self.queued()
        for bad in ({**review,'previous_revision':'b'*64},{**review,'revision':'b'*64},
                    {**review,'manifest_sha256':'b'*64},{**review,'approved':True},
                    {**review,'reviewer':''}):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                runner.review_queue(self.host,bad)
        with sqlite3.connect(runner.database(self.host)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM queue_reviews').fetchone()[0],0)

    def test_review_is_immutable_and_duplicate_review_cannot_rewind_source(self):
        review=self.queued()
        runner.review_queue(self.host,review)
        with self.assertRaises(ValueError):
            runner.review_queue(self.host,review)
        with sqlite3.connect(runner.database(self.host)) as db:
            for sql in ('DELETE FROM queue_reviews','UPDATE queue_reviews SET review=\'{}\''):
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(sql)

    def test_bridge_exposes_explicit_review_without_model_calls(self):
        review=self.queued()
        path=self.host.directory/'operator-review.json'
        path.write_text(json.dumps(review))
        with patch.object(sys,'argv',['agentos_bridge.py','autoresearch-review-queue','--state',str(self.host.directory),'--review',str(path)]), \
             patch.object(bridge,'publish'),patch.object(bridge,'native') as native,redirect_stdout(io.StringIO()) as output:
            bridge.main()
        self.assertEqual(json.loads(output.getvalue())['status'],'queue_revision_reviewed')
        native.assert_not_called()


if __name__=='__main__':
    unittest.main()
