import unittest
import test_memory_retrieval_v18 as fixtures
from nerve_awim.adaptive_memory import OutcomeMemoryRanker
from nerve_awim.learning_study import Episode, run_study, validate_stream
from nerve_awim.recipe_selection import select_recipe
from nerve_awim.skill_proposals import propose_skill
from scripts.adaptive_memory_study import run


class StudyTests(unittest.TestCase):
    def stream(self):
        return [Episode(str(n), 'train' if n < 3 else 'evaluation', {'number': n}, n) for n in range(8)]

    def test_fixture_uses_real_memory_without_manufacturing_gain(self):
        report = run()
        self.assertTrue(all(row['accuracy'] == 1 for row in report['arms'].values()))
        self.assertEqual(report['paired_adaptive']['no_memory'], {'wins': 0, 'losses': 0})
        self.assertFalse(report['promotion_authorized'])

    def test_evaluation_feedback_and_answers_never_reach_predictor(self):
        calls = []
        class Arm:
            def predict(self, task):
                if set(task) != {'number'}:
                    raise AssertionError('expected answer leaked')
                return task['number']
            def learn(self, task, output, success, episode_id):
                calls.append(episode_id)
        run_study(self.stream(), arm_factory=lambda name: Arm(), judge=lambda task, output, expected: output == expected)
        self.assertEqual(calls, ['0','1','2']*3)

    def test_duplicates_and_post_evaluation_training_rejected(self):
        stream = self.stream()
        stream[-1] = Episode('new', 'evaluation', stream[0].task, 0)
        with self.assertRaises(ValueError):
            validate_stream(stream)
        stream = self.stream()
        stream[-1] = Episode('7', 'train', {'number': 7}, 7)
        with self.assertRaises(ValueError):
            validate_stream(stream)

    def test_recipe_selection_budget_ties_and_no_promotion(self):
        recipes = [{'prompt':'first', 'strategy':'known'}, {'prompt':'second', 'strategy':'known'}]
        result = select_recipe(recipes, [1,2,3], evaluate=lambda recipe, task: True)
        self.assertEqual(result['recipe'], recipes[0])
        self.assertFalse(result['improved_on_selection'])
        self.assertFalse(result['promotion_authorized'])
        with self.assertRaises(ValueError):
            select_recipe(recipes, [1,2,3], evaluate=lambda *args: self.fail('budget exceeded'), max_calls=5)

    def test_bad_evaluator_cannot_select_recipe(self):
        recipes = [{'prompt':'first', 'strategy':'known'}, {'prompt':'second', 'strategy':'known'}]
        with self.assertRaises(ValueError):
            select_recipe(recipes, [1,2,3], evaluate=lambda *args: 'yes')


class SkillTests(unittest.TestCase):
    setUp = fixtures.SemanticMemoryV18Tests.setUp
    new = fixtures.SemanticMemoryV18Tests.new

    def seed(self):
        mid = self.new('sorting advice')
        ranker = OutcomeMemoryRanker(self.host, evaluator=lambda *args: True, evaluator_revision='test-v1')
        for n in range(3):
            ranker.observe(self.reviewer, memory_id=mid, episode_id='case-'+str(n), task={'number':n}, output=n)
        return mid

    def test_skill_is_pending_with_successful_evidence(self):
        self.seed()
        mid = propose_skill(self.host, self.writer, context='planning', lesson='Use the requested sorting direction.',
                            episodes=['case-0','case-1','case-2'], evaluator_revision='test-v1')
        record = self.host.status(self.writer, mid)
        self.assertEqual((record.status, record.kind), ('pending', 'procedural'))

    def test_cross_scope_stale_revision_and_revocation_rejected(self):
        mid = self.seed()
        kwargs = dict(context='planning', lesson='sorting lesson', episodes=['case-0','case-1','case-2'], evaluator_revision='test-v1')
        with self.assertRaises(ValueError):
            propose_skill(self.host, self.outside, **kwargs)
        with self.assertRaises(ValueError):
            propose_skill(self.host, self.writer, **{**kwargs, 'evaluator_revision':'test-v2'})
        self.host.revoke(self.reviewer, mid, evaluator_id='test')
        with self.assertRaises(ValueError):
            propose_skill(self.host, self.writer, **kwargs)
