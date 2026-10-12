import unittest

from nerve_awim.memory_gateway.evaluation import GatewayMemoryObjective, run_gateway_research
from nerve_awim.recursive_evolution_v19 import RetrievalGenome


class GatewayEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.objective = GatewayMemoryObjective()
        self.addCleanup(self.objective.close)

    def test_real_gateway_scope_and_revocation_affect_evaluation(self):
        self.assertEqual(self.objective.corpus(foreign=True), {})
        before = self.objective.evaluate(RetrievalGenome(), 'train')
        self.assertEqual(before.cross_tenant_leaks, 0)
        self.assertGreater(before.hits, 0)
        self.objective.gateway.revoke_actor(self.objective.actor)
        with self.assertRaises(PermissionError):
            self.objective.evaluate(RetrievalGenome(), 'validation')

    def test_final_comparison_is_consumed_once_and_prevents_retuning(self):
        genome = RetrievalGenome()
        self.objective.evaluate(genome, 'validation')
        self.objective.evaluate(genome, 'holdout')
        self.objective.evaluate(genome, 'holdout')
        for split in ('train', 'validation', 'holdout'):
            with self.assertRaises(RuntimeError):
                self.objective.evaluate(genome, split)

    def test_unknown_schema_or_split_rejected(self):
        for genome, split in (({'token_weight': 3}, 'train'), (RetrievalGenome(), 'private')):
            with self.assertRaises(ValueError):
                self.objective.evaluate(genome, split)

    def test_existing_loop_returns_review_only_reproducible_lineage(self):
        first = run_gateway_research(generations=2, seed=19)
        second = run_gateway_research(generations=2, seed=19)
        self.assertEqual(first, second)
        self.assertLessEqual(first['generations_run'], 2)
        self.assertFalse(first['deployed'])
        self.assertFalse(first['runtime_kv_tested'])
        self.assertFalse(first['holdout_sealed'])
        self.assertIn(first['status'], ('candidate_for_human_review', 'no_verified_improvement'))
        self.assertEqual(first['report_only_holdout']['cross_tenant_leaks'], 0)
