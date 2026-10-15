"""Real scoped episode storage; receipt transport is mocked only in graph tests."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.memory_gateway import scientific_format_feedback as feedback
from nerve_awim.memory_gateway.experience_store_v2 import ExperienceStoreV2
from nerve_awim.memory_gateway.gateway import MemoryGateway
from nerve_awim.memory_gateway.contracts import MemoryScope
from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger
from test_experience_store_v2 import episode
from test_scientific_format_episode_import import receipt


class FormatFeedbackTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.auth = MemoryAuthority()
        self.actor = self.auth.issue('tenant', 'agent', permissions=('read', 'propose'))
        gateway = MemoryGateway(TrustedMemoryLedger(self.root / 'authority.sqlite', self.auth))
        self.store = ExperienceStoreV2(self.root / 'store.sqlite', gateway,
                                       MemoryScope('tenant', 'agent', 'format-feedback'))
        self.store.initialize(self.actor)

    def rows(self):
        result = [episode(i) for i in range(4)]
        for i, row in enumerate(result):
            row['failure_class'] = 'schema_shape_failure' if i % 2 else 'abstention_contract_failure'
            row['schema_ok'] = i % 2 == 0
            row['stratum'] = 'supported-measurement' if i < 2 else 'unit-mismatch'
        return result

    def test_exact_rules_all_members_and_policy_identity(self):
        self.store.append_many(self.actor, self.rows())
        result = feedback.propose(self.store, self.actor, 'd' * 64)
        self.assertEqual(len(result['proposals']), 2)
        by_failure = {p['failure_class']: p for p in result['proposals']}
        for failure, (mutation, constrained) in feedback.RULES.items():
            proposal = by_failure[failure]
            self.assertEqual(proposal['mutation'], mutation)
            self.assertEqual(proposal['execution_policy']['constrained'], constrained)
            self.assertEqual(len(proposal['clusters']), 2)
            self.assertEqual(sum(len(c['members']) for c in proposal['clusters']), 2)
            self.assertTrue(feedback.validate_proposal(proposal, self.store, self.actor, 'd' * 64))
            self.assertFalse(proposal['evaluated'])
            self.assertFalse(proposal['promotion_authorized'])
        self.assertFalse(result['negative_evidence_enforced'])

    def test_empty_and_disabled_paths(self):
        self.assertEqual(feedback.propose(self.store, self.actor, 'd' * 64)['proposals'], [])
        with patch.object(feedback.importer, 'run', side_effect=AssertionError('no IO')):
            self.assertEqual(feedback.run('a', 'b', 'c', 'd', 'bad', disabled=True),
                             {'status': 'off', 'new_model_calls': 0})
        with self.assertRaises(ValueError):
            feedback.run('a', 'b', 'c', 'd', 'bad', disabled=1)

    def test_mutated_proposal_model_or_cluster_rejected(self):
        self.store.append_many(self.actor, self.rows())
        proposal = feedback.propose(self.store, self.actor, 'd' * 64)['proposals'][0]
        for field, value in [('evaluated', True), ('promotion_authorized', True), ('store_head', 'a' * 64)]:
            changed = deepcopy(proposal); changed[field] = value
            with self.assertRaises(ValueError):
                feedback.validate_proposal(changed, self.store, self.actor, 'd' * 64)
        with self.assertRaises(ValueError):
            feedback.validate_proposal(proposal, self.store, self.actor, 'e' * 64)
        changed = deepcopy(proposal); changed['clusters'][0]['members'].clear()
        with self.assertRaises(ValueError):
            feedback.validate_proposal(changed, self.store, self.actor, 'd' * 64)

    def test_revocation_and_changed_store_reject_old_proposal(self):
        self.store.append_many(self.actor, self.rows())
        proposal = feedback.propose(self.store, self.actor, 'd' * 64)['proposals'][0]
        added = episode(0); added['episode_id'] = 'later'
        self.store.append_many(self.actor, [added])
        with self.assertRaises(ValueError):
            feedback.validate_proposal(proposal, self.store, self.actor, 'd' * 64)
        self.auth.revoke(self.actor)
        with self.assertRaises(PermissionError):
            feedback.propose(self.store, self.actor, 'd' * 64)

    def test_unknown_failure_does_not_invent_mutation(self):
        self.store.append_many(self.actor, [episode(0)])
        self.assertEqual(feedback.propose(self.store, self.actor, 'd' * 64)['proposals'], [])

    def test_mutated_rules_and_bad_model_rejected(self):
        with patch.dict(feedback.RULES, {'unapproved': ('format_contract', False)}):
            with self.assertRaises(ValueError): feedback.propose(self.store, self.actor, 'd' * 64)
        with self.assertRaises(ValueError): feedback.propose(self.store, self.actor, 'short')

    def test_full_import_to_proposal_graph_restart_without_inference(self):
        paths = [self.root / name for name in ('feedback', 'episodes', 'study', 'study.sqlite')]
        with patch.object(feedback.importer.study, 'validate_receipt', return_value=receipt()), \
                patch.object(feedback.importer.study, 'run', side_effect=AssertionError('no dispatch')), \
                patch.object(feedback.importer.study.transport, 'run', side_effect=AssertionError('no model')):
            report = feedback.run(*paths, 'd' * 64)
            self.assertEqual(report['status'], 'registered')
            self.assertEqual(len(report['generation']['proposals']), 2)
            files = [p for root in paths[:2] for p in root.iterdir() if p.name != 'supervisor.lock']
            before = {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in files}
            self.assertEqual(feedback.run(*paths, 'd' * 64), report)
            self.assertEqual({str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in files}, before)
            (paths[0] / 'report.json').write_text('{}\n')
            with self.assertRaises(ValueError): feedback.run(*paths, 'd' * 64)
            self.assertEqual((paths[0] / 'report.json').read_text(), '{}\n')

    def test_missing_source_and_overlapping_paths_fail_before_output(self):
        paths = [self.root / name for name in ('feedback', 'episodes', 'study', 'study.sqlite')]
        with patch.object(feedback.importer.study, 'run', side_effect=AssertionError('no dispatch')):
            with self.assertRaises(ValueError): feedback.run(*paths, 'd' * 64)
        self.assertFalse(paths[0].exists()); self.assertFalse(paths[1].exists())
        with self.assertRaises(ValueError):
            feedback.run(paths[0], paths[0] / 'episodes', paths[2], paths[3], 'd' * 64)


if __name__ == '__main__': unittest.main()
