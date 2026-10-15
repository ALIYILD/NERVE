"""Dataset/host integration using offline adapters; no live evidence is asserted."""
from dataclasses import replace
import itertools
import json
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import Mock, patch

from nerve_awim.cue_cycle import DiscoveryReceipt, run_cue_cycle
from nerve_awim.cue_dataset import parse_dataset_json
from nerve_awim.cue_evaluation import ModelParity
from nerve_awim.cue_experiment import ProviderReceipt, JudgeReceipt
from nerve_awim.cue_host import CueHost
from nerve_awim.cue_learning import GovernedCueCoordinator
import test_cue_learning as learning_fixtures
import test_cue_host as host_fixtures


def dataset_record():
    return {'schema_version': 1, 'dataset_id': 'cycle-fixture-v1',
            'source': {'uri': 'fixture:offline', 'revision': 'fixture-1'},
            'splits': {split: [{'task_id': split + str(i), 'family_id': split + '-family-' + str(i),
                                'instruction': 'Question ' + split + str(i), 'expected': 'fixture-answer'}
                               for i in range(30 if split == 'holdout' else 1)]
                       for split in ('discovery', 'selection', 'holdout')}}


def dataset(record=None):
    return parse_dataset_json(json.dumps(dataset_record() if record is None else record))


def adapters(model, *, gain=True):
    discovery = Mock(return_value=DiscoveryReceipt({'candidates': ['Check the reasoning.']}, .01, False))
    def dispatch(request):
        correct = request.arm == 'candidate' or not gain
        return ProviderReceipt('fixture-answer' if correct else 'wrong', float(correct), model,
            .009 if request.arm == 'candidate' else .01,
            request.task_id + request.arm, False, False, request.cue_digest, request.arm)
    provider = Mock(side_effect=dispatch)
    judge = Mock(side_effect=lambda output, expected: JudgeReceipt(output == expected, True))
    ticks = itertools.count()
    settings = {'model': model, 'discovery_execute': discovery, 'provider': provider, 'judge': judge,
                'generator_id': 'generator', 'evaluator_id': 'independent', 'max_calls': 63,
                'max_cost_usd': 1, 'discovery_cost_cap_usd': .1, 'per_call_cost_cap_usd': .01,
                'permission_granted': True, 'experiment_clock': lambda: next(ticks)}
    return settings, discovery, provider, judge


class DatasetCycleIntegrationTests(unittest.TestCase):
    setUp = learning_fixtures.CueLearningTests.setUp

    def invoke(self, data, settings, **changes):
        values = dict(settings, profile=self.profile, task_type='research', dataset=data,
                      manifest=data.manifest, selection_tasks=data.selection_tasks,
                      holdout_tasks=data.holdout_tasks)
        values.update(changes)
        return run_cue_cycle(self.cce, self.actors['trainer'], self.actors['evaluator'], **values)

    def test_task_answer_and_order_must_match_dataset_before_any_dispatch(self):
        data = dataset()
        settings, discovery, provider, judge = adapters(self.model)
        changed_answer = (replace(data.selection_tasks[0], expected='altered'),)
        for change in ({'selection_tasks': changed_answer},
                       {'holdout_tasks': tuple(reversed(data.holdout_tasks))},
                       {'dataset': replace(data, digest='0' * 64)}):
            with self.assertRaises(ValueError):
                self.invoke(data, settings, **change)
        discovery.assert_not_called(); provider.assert_not_called(); judge.assert_not_called()
        with self.engine._db() as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM cce_dataset_studies').fetchone()[0], 0)

    def test_reservation_precedes_failure_and_burns_holdout_despite_renamed_ids(self):
        data = dataset()
        settings, discovery, provider, judge = adapters(self.model)
        def fail_after_reservation(*args, **kwargs):
            with self.engine._db() as con:
                rows = con.execute('SELECT dataset_digest FROM cce_dataset_studies').fetchall()
                self.assertEqual([row[0] for row in rows], [data.digest])
                self.assertGreater(con.execute('SELECT COUNT(*) FROM cce_dataset_fingerprints').fetchone()[0], 0)
            raise RuntimeError('private adapter exception')
        discovery.side_effect = fail_after_reservation
        result = self.invoke(data, settings)
        self.assertEqual(result['state'], 'blocked')
        self.assertEqual(result['dataset_digest'], data.digest)
        self.assertEqual(result['attempted_calls'], 1)
        self.assertNotIn('private adapter', str(result))
        provider.assert_not_called(); judge.assert_not_called()
        # Reopen coordinator to ensure this is persisted protection, not a cache.
        self.cce = GovernedCueCoordinator(self.engine, enabled=True)
        renamed = dataset_record()
        renamed['dataset_id'] = 'renamed-fixture'
        for tasks in renamed['splits'].values():
            for task in tasks:
                task['task_id'] = 'new-' + task['task_id']
                task['family_id'] = 'new-' + task['family_id']
        retry_settings, retry_discovery, retry_provider, retry_judge = adapters(self.model)
        with self.assertRaisesRegex(ValueError, 'content/family'):
            self.invoke(dataset(renamed), retry_settings)
        retry_discovery.assert_not_called(); retry_provider.assert_not_called(); retry_judge.assert_not_called()

    def test_family_reuse_blocks_paraphrased_holdout_and_changed_ids(self):
        data = dataset()
        settings, discovery, provider, judge = adapters(self.model)
        discovery.return_value = DiscoveryReceipt({'candidates': []}, .01, False)
        first = self.invoke(data, settings)
        self.assertEqual(first['reason'], 'no_candidate')
        changed = dataset_record()
        for tasks in changed['splits'].values():
            for task in tasks:
                task['task_id'] = 'renamed-' + task['task_id']
                task['instruction'] += ' rewritten'
        discovery.reset_mock()
        with self.assertRaisesRegex(ValueError, 'content/family'):
            self.invoke(dataset(changed), settings)
        discovery.assert_not_called(); provider.assert_not_called(); judge.assert_not_called()

    def test_complete_dataset_cycle_preserves_digest_without_automatic_activation(self):
        data = dataset()
        settings, discovery, provider, judge = adapters(self.model)
        result = self.invoke(data, settings)
        self.assertEqual(result['state'], 'awaiting_approval')
        self.assertEqual(result['dataset_digest'], data.digest)
        self.assertFalse(result['activated'])
        self.assertEqual(provider.call_count, 62)
        self.assertEqual(judge.call_count, 62)
        self.assertEqual(discovery.call_args.args[1], {'operation': 'propose_cognitive_cues',
                         'discovery_ids': ['discovery0'], 'max_candidates': 1})
        self.assertNotIn('fixture-answer', str(discovery.call_args))
        self.assertNotIn('Question ', str(result))
        with self.engine._db() as con:
            row = con.execute('SELECT dataset_digest,candidate FROM cce_dataset_studies').fetchone()
            self.assertEqual(tuple(row), (data.digest, result['candidate']))
        self.assertIsNone(self.cce.select(self.actors['runtime'], self.profile, 'research', permission_granted=True).cue)


class DatasetHostIntegrationTests(unittest.TestCase):
    setUp = host_fixtures.CueHostTests.setUp
    configure = host_fixtures.CueHostTests.configure

    def test_installed_bridge_dataset_status_is_provider_free(self):
        import subprocess
        import sys
        script=Path(__file__).resolve().parents[1]/'scripts/agentos_bridge.py'
        process=subprocess.run([sys.executable,str(script),'cce-dataset-status',
            '--state',self.temp.name,'--profile','worker'],capture_output=True,text=True,timeout=20)
        self.assertEqual(process.returncode,0,process.stderr)
        result=json.loads(process.stdout)
        self.assertEqual(result['protection'],'legacy_ids')
        self.assertEqual(result['dataset_studies'],0)
        with sqlite3.connect(self.host.path) as con:
            tables={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertNotIn('cce_dataset_studies',tables)

    def settings(self, gain=False):
        model = ModelParity('fixture', 'model', 'revision-1', 'tokenizer', 'tokens-1',
                            'template-hash', 'sampling-hash', 0, 100, 'context-hash', self.profile.key)
        return adapters(model, gain=gain)

    def test_dataset_host_scopes_handoff_and_persists_rejection_summary_and_memory(self):
        self.configure()
        data = dataset()
        settings, discovery, provider, judge = self.settings()
        result = self.adapter.run_dataset_cycle('worker', data, **settings)
        self.assertEqual(result['state'], 'rejected')
        self.assertEqual(result['reason'], 'selection_gate_failed')
        self.assertEqual(result['dataset_digest'], data.digest)
        self.assertEqual(result['attempted_calls'], 3)
        self.assertEqual(discovery.call_args.kwargs['tenant'], 'agentos-local')
        self.assertEqual(discovery.call_args.kwargs['agent'], 'worker')
        self.assertEqual(self.adapter.inspect('worker', result['candidate'])['task_type'], 'handoff')
        self.assertEqual(self.adapter.inspect('worker', result['candidate'])['status'], 'rejected')
        self.assertEqual(json.loads((Path(self.temp.name) / 'cce-last-cycle.json').read_text()), result)
        self.assertEqual(self.host.ledger.status(self.host.actor('worker'), result['memory_id']).status, 'pending')
        self.assertIsNone(self.adapter.route_status('worker')['active'])
        self.assertEqual(provider.call_count, 2)
        self.assertNotIn('fixture-answer', str(discovery.call_args))

    def test_dataset_host_rejects_task_override_without_bootstrap_or_dispatch(self):
        self.configure()
        data = dataset()
        settings, discovery, provider, judge = self.settings()
        with self.assertRaises(ValueError):
            self.adapter.run_dataset_cycle('worker', data, selection_tasks=data.selection_tasks, **settings)
        self.assertIsNone(self.adapter._engine)
        discovery.assert_not_called(); provider.assert_not_called(); judge.assert_not_called()

    def test_dataset_status_does_not_bootstrap_write_or_dispatch(self):
        self.configure()
        def dump():
            with sqlite3.connect(self.host.path) as con:
                return tuple(con.iterdump())
        before = dump()
        with patch('nerve_awim.cue_cycle.run_cue_cycle', side_effect=AssertionError('no provider work')):
            status = self.adapter.dataset_status('worker')
        self.assertEqual(before, dump())
        self.assertIsNone(self.adapter._engine)
        self.assertEqual(status['dataset_studies'], 0)
        settings, discovery, provider, judge = self.settings()
        self.adapter.run_dataset_cycle('worker', dataset(), **settings)
        reloaded = CueHost(self.host)
        before = dump()
        with patch('nerve_awim.cue_cycle.run_cue_cycle', side_effect=AssertionError('no provider work')):
            status = reloaded.dataset_status('worker')
            foreign = reloaded.dataset_status('other')
        self.assertEqual(before, dump())
        self.assertIsNone(reloaded._engine)
        self.assertEqual(status['protection'], 'content_and_family')
        self.assertEqual(status['dataset_studies'], 1)
        self.assertEqual(status['content_fingerprints'], 32)
        self.assertEqual(status['family_fingerprints'], 32)
        self.assertEqual(foreign['dataset_studies'], 0)
        self.assertNotIn('Question ', str(status))


if __name__ == '__main__':
    unittest.main()
