import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from nerve_awim.skill_model import LessonModelAdapter
from nerve_awim.skill_validation import evaluate_lesson
from nerve_awim.learning_study import Episode


class AdapterTests(unittest.TestCase):
    request = {'context': 'test', 'evidence': [{'episode_id': str(n)} for n in range(3)]}
    response = json.dumps({'lesson': 'Check the direction.', 'episodes': ['0', '1', '2']})

    def adapter(self, complete, **kwargs):
        return LessonModelAdapter(complete=complete, model='host-selected', **kwargs)

    def test_disabled_by_default(self):
        with self.assertRaises(PermissionError):
            self.adapter(lambda _: self.fail('disabled'))(self.request)

    def test_request_limits_and_schema(self):
        calls = []
        adapter = self.adapter(lambda request: calls.append(request) or self.response, enabled=True)
        self.assertEqual(adapter(self.request)['lesson'], 'Check the direction.')
        self.assertEqual(calls[0]['timeout_seconds'], 30)
        self.assertEqual(json.loads(calls[0]['input']), self.request)
        with self.assertRaises(RuntimeError):
            adapter(self.request)

    def test_bad_responses_consume_quota(self):
        for raw in ('{}', 'not json', '{"lesson":"a","lesson":"b","episodes":[]}',
                    json.dumps({'lesson': 'a', 'episodes': ['invented']}), 'x'*16385,
                    '{"lesson":NaN,"episodes":[]}'):
            adapter = self.adapter(lambda _: raw, enabled=True)
            with self.assertRaises(ValueError):
                adapter(self.request)
            with self.assertRaises(RuntimeError):
                adapter(self.request)

    def test_transport_failure_consumes_quota(self):
        def fail(_):
            raise TimeoutError('transport')
        adapter = self.adapter(fail, enabled=True)
        with self.assertRaises(TimeoutError):
            adapter(self.request)
        with self.assertRaises(RuntimeError):
            adapter(self.request)

    def test_concurrent_quota(self):
        adapter = self.adapter(lambda _: self.response, enabled=True, max_calls=3)
        def attempt(_):
            try:
                adapter(self.request)
                return True
            except RuntimeError:
                return False
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(attempt, range(20))), 3)

    def test_oversize_input_never_calls_transport(self):
        adapter = self.adapter(lambda _: self.fail('oversize'), enabled=True)
        with self.assertRaises(ValueError):
            adapter({'text': 'x'*65537})


class ValidationTests(unittest.TestCase):
    def stream(self):
        return [Episode(str(n), 'train' if n < 3 else 'evaluation', {'n': n}, n) for n in range(8)]

    def test_paired_comparison_no_answers_or_training_calls(self):
        calls = []
        def predict(task, lesson):
            self.assertEqual(set(task), {'n'})
            self.assertGreaterEqual(task['n'], 3)
            calls.append(lesson)
            return task['n'] if lesson else -1
        report = evaluate_lesson('candidate', self.stream(), predict=predict,
                                 judge=lambda task, output, expected: output == expected)
        self.assertEqual((report['wins'], report['losses']), (5, 0))
        self.assertEqual(calls[:4], [None, 'candidate', 'candidate', None])
        self.assertFalse(report['promotion_authorized'])

    def test_overlap_and_budget_reject_before_prediction(self):
        kwargs = dict(predict=lambda *args: self.fail('must not call'), judge=lambda *args: True)
        with self.assertRaises(ValueError):
            evaluate_lesson('candidate', self.stream(), max_calls=9, **kwargs)
        stream = self.stream()
        stream[-1] = Episode('7', 'evaluation', stream[0].task, 0)
        with self.assertRaises(ValueError):
            evaluate_lesson('candidate', stream, **kwargs)

    def test_invalid_judge_aborts_without_report(self):
        with self.assertRaises(ValueError):
            evaluate_lesson('candidate', self.stream(), predict=lambda *args: 0,
                            judge=lambda *args: 'yes')

    def test_regression_is_reported(self):
        report = evaluate_lesson('bad lesson', self.stream(),
            predict=lambda task, lesson: -1 if lesson else task['n'],
            judge=lambda task, output, expected: output == expected)
        self.assertEqual((report['wins'], report['losses']), (0, 5))
