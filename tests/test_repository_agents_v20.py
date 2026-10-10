"""Independent token judge and actual repository-task lifecycle verification."""
import unittest

from nerve_awim.repository_agents_v20 import ast_inventory, token_inventory, regex_inventory
from benchmarks.v20_governed_repository_learning import benchmark, TRAIN_PATHS, HOLDOUT_PATHS


class RepositoryAgentsTests(unittest.TestCase):
    def test_inventory_excludes_methods_nested_defs_strings_and_comments(self):
        source = '''# def fake_comment():
text = "def fake_string():"
class Example:
    def method(self):
        pass
async def top_async():
    def nested():
        pass
    return nested
@decorator
def top_sync():
    pass
'''
        self.assertEqual(ast_inventory(source), ['top_async', 'top_sync'])
        self.assertEqual(token_inventory(source), ['top_async', 'top_sync'])
        self.assertIn('method', regex_inventory(source))

    def test_real_source_tasks_holdout_and_rollback(self):
        self.assertFalse(set(TRAIN_PATHS) & set(HOLDOUT_PATHS))
        result = benchmark()
        self.assertEqual(result['evaluation']['status'], 'passed')
        self.assertTrue(result['approved_route_executed'])
        self.assertTrue(result['rollback_restored_original_behaviour'])
        metrics = result['evaluation']['contexts']['python_top_level_functions']
        self.assertGreater(metrics['candidate_hits'], metrics['baseline_hits'])
        # Expose the capable fixed control instead of claiming learning beats it.
        self.assertEqual(metrics['candidate_hits'], result['capable_fixed_control']['hits'])
        self.assertEqual(len(result['source_manifest_sha256']), 12)


if __name__ == '__main__':
    unittest.main()
