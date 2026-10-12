"""Independent token judge and actual repository-task lifecycle verification."""
import unittest
from unittest.mock import patch

from nerve_awim.agent_learning_v12 import AgentTask
from nerve_awim.repository_agents_v20 import CONTEXT, ast_inventory, token_inventory, regex_inventory, repository_judge
from benchmarks.v20_governed_repository_learning import benchmark, TRAIN_PATHS, HOLDOUT_PATHS


class RepositoryAgentsTests(unittest.TestCase):
    def test_unicode_identifiers_match_python_normalization(self):
        for source, expected in (
            ('def K(): pass', ['K']),
            ('async def 𝒇(): pass', ['f']),
            ('def cafe\u0301(): pass', ['café']),
            ('def a\u0301b\u0327(): pass', ['áb̧']),
            ('def Ａ(): pass\ndef A(): pass', ['A']),
            ('def 東京(): pass', ['東京']),
        ):
            with self.subTest(source=source):
                self.assertEqual(ast_inventory(source), expected)
                self.assertEqual(token_inventory(source), expected)

    def test_unicode_judge_stays_independent_and_rejects_wrong_spelling(self):
        task = AgentTask('unicode', CONTEXT, 'def K(): pass')
        with patch('nerve_awim.repository_agents_v20.ast.parse', side_effect=AssertionError('not independent')):
            self.assertTrue(repository_judge(task, ['K']))
            self.assertFalse(repository_judge(task, ['K']))

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
