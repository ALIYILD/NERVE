import json
import unittest
import test_memory_retrieval_v18 as fixtures
from nerve_awim.hermes_agents import HermesAgentRuntime, ROLES, load_pinned_factory
from nerve_awim.hermes_learning import propose_and_evaluate
from nerve_awim.adaptive_memory import OutcomeMemoryRanker
from nerve_awim.learning_study import Episode


class FakeHermes:
    instances = []
    def __init__(self, **kwargs):
        self.config, self.tools, self.closed = kwargs, [], False
        self.instances.append(self)
    def run_conversation(self, message, **kwargs):
        self.request = json.loads(message)
        self.turn = kwargs
        episodes = [e['episode_id'] for e in self.request.get('evidence', [])]
        if 'Summarize supplied' in kwargs['system_message']:
            result = {'summary':'Supplied records describe successful sorting.', 'episodes':episodes}
        else:
            result = {'lesson':'Respect sorting direction.', 'episodes':episodes}
        return {'completed':True, 'final_response':json.dumps(result)}
    def close(self):
        self.closed = True


def runtime(factory=FakeHermes, enabled=True):
    return HermesAgentRuntime(factory, model='offline-test', provider='test',
                              base_url='http://localhost:1', enabled=enabled)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        FakeHermes.instances.clear()
    def test_disabled_loader_and_runtime_do_not_execute(self):
        with self.assertRaises(PermissionError):
            load_pinned_factory('/does-not-exist')
        with self.assertRaises(PermissionError):
            runtime(enabled=False).execute('research', {}, tenant='t', agent='a')
        self.assertEqual(FakeHermes.instances, [])
    def test_fresh_sessions_and_bounded_constructor(self):
        agent = runtime()
        for _ in range(2):
            agent.execute('research', {}, tenant='t', agent='a')
        a, b = FakeHermes.instances
        self.assertNotEqual(a.config['session_id'], b.config['session_id'])
        self.assertTrue(a.config['skip_memory'])
        self.assertEqual(a.config['enabled_toolsets'], [])
        self.assertEqual(a.config['max_iterations'], 2)
        self.assertTrue(a.closed and b.closed)
    def test_unexpected_tools_rejected_and_closed(self):
        class Tools(FakeHermes):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.tools = ['shell']
        with self.assertRaises(PermissionError):
            runtime(Tools).execute('research', {}, tenant='t', agent='a')
        self.assertTrue(FakeHermes.instances[-1].closed)
    def test_incomplete_turn_rejected(self):
        class Failed(FakeHermes):
            def run_conversation(self, *args, **kwargs):
                return {'completed':False, 'final_response':'{}'}
        with self.assertRaises(ValueError):
            runtime(Failed).execute('research', {}, tenant='t', agent='a')
        self.assertTrue(FakeHermes.instances[-1].closed)
    def test_role_registry_and_quota(self):
        self.assertEqual(len(ROLES), 7)
        agent = runtime()
        for _ in range(10):
            agent.execute('research', {}, tenant='t', agent='a')
        with self.assertRaises(RuntimeError):
            agent.execute('research', {}, tenant='t', agent='a')
        with self.assertRaises(ValueError):
            agent.execute('admin', {}, tenant='t', agent='a')


class WorkflowTests(unittest.TestCase):
    setUp = fixtures.SemanticMemoryV18Tests.setUp
    new = fixtures.SemanticMemoryV18Tests.new
    def seed(self):
        FakeHermes.instances.clear()
        mid = self.new('sorting evidence')
        ranker = OutcomeMemoryRanker(self.host, evaluator=lambda *args: True, evaluator_revision='test-v1')
        for n in range(3):
            ranker.observe(self.reviewer, memory_id=mid, episode_id='case-'+str(n), task={'n':n}, output=n)
        return mid
    def workflow(self, adapter=None, judge=None):
        return propose_and_evaluate(self.host, self.writer, runtime=adapter or runtime(), context='planning',
            evidence_episodes=['case-0','case-1','case-2'], evaluator_revision='test-v1',
            study=[Episode(str(n), 'train' if n<3 else 'evaluation', {'n':n}, n) for n in range(8)],
            predict=lambda task, lesson: task['n'], judge=judge or (lambda task, output, expected: output==expected))
    def test_research_proposal_evaluation_stays_pending(self):
        self.seed()
        report = self.workflow()
        self.assertEqual(report['memory_status'], 'pending')
        self.assertEqual(report['evaluation']['wins'], 0)
        self.assertFalse(report['promotion_authorized'])
        self.assertEqual(len(FakeHermes.instances), 2)
        for instance in FakeHermes.instances:
            self.assertNotIn('expected', instance.request)
            self.assertNotIn('study', instance.request)
    def test_forged_research_references_rejected(self):
        self.seed()
        class Forged(FakeHermes):
            def run_conversation(self, *args, **kwargs):
                return {'completed':True, 'final_response':'{"summary":"claim","episodes":["fake"]}'}
        with self.assertRaises(ValueError):
            self.workflow(runtime(Forged))
    def test_judge_failure_cannot_approve_proposal(self):
        self.seed()
        with self.assertRaises(ValueError):
            self.workflow(judge=lambda *args: 'yes')
        import sqlite3
        with sqlite3.connect(self.host.path) as con:
            statuses = con.execute("SELECT status FROM trusted_memory_v18 WHERE source_id='verified-episode-proposal'").fetchall()
        self.assertEqual(statuses, [('pending',)])
