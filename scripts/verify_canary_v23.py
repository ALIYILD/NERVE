"""Reproducible local canary/fallback drill with real repository-file tasks.

Uses a deliberately weaker initial tool to exercise the passed-candidate path.
Fixed trial IDs and injected judge failure are test fixtures, not live evidence.
"""
from pathlib import Path
import json
import tempfile
from unittest.mock import patch
from uuid import UUID

from nerve_awim.canary_learning_v23 import CanaryLearning
from nerve_awim.governed_learning_v20 import GovernedLearning, LearningAuthority
from nerve_awim.repository_agents_v20 import CONTEXT, REPOSITORY_STRATEGIES, repository_judge
from nerve_awim.repository_pilot_v22 import file_task

ROOT = Path(__file__).resolve().parents[1]
TRAIN = ('agent_learning_v12.py', 'agent_bridge_v13.py', 'core.py')
HOLDOUT = ('recovery_learning_v17.py', 'memory_retrieval_v18.py', 'learn_v31.py',
           'calibration_v15.py', 'autoresearch_v05.py')


def verify():
    with tempfile.TemporaryDirectory() as folder:
        auth = LearningAuthority()
        actors = {r: auth.issue('test-repository', 'inventory', r)
                  for r in ('trainer', 'evaluator', 'operator', 'runtime', 'auditor')}
        engine = GovernedLearning(Path(folder) / 'canary.db', authority=auth,
            strategies=REPOSITORY_STRATEGIES, judge=repository_judge,
            baseline_routes={CONTEXT: 'regex-inventory'}, contract_revision='canary-drill-v2')
        baseline = engine.bootstrap(actors['operator'])
        for name in TRAIN:
            engine.learn_from_task(actors['trainer'], file_task(ROOT, 'src/nerve_awim/' + name))
        candidate = engine.freeze_candidate(actors['trainer'])
        engine.evaluate_candidate(actors['evaluator'], candidate,
            [file_task(ROOT, 'src/nerve_awim/' + name) for name in HOLDOUT])
        controller = CanaryLearning(engine)
        with patch('nerve_awim.canary_learning_v23.uuid.uuid4', side_effect=(UUID(int=23), UUID(int=24))):
            trial = controller.start(actors['operator'], candidate, expected_generation=0,
                reason='simulated-operator-drill', percent=25, required_successes=20)
        accepted, fallback = 0, False
        for path in sorted((ROOT / 'src/nerve_awim').glob('*.py')):
            if path.name in (*TRAIN, *HOLDOUT):
                continue
            try:
                task = file_task(ROOT, str(path.relative_to(ROOT)))
                engine._task(task)
            except ValueError:
                continue
            result = controller.execute(actors['runtime'], trial, task)
            if result['canary']['used']:
                accepted += 1
                # Simulate an independent quality check finding a regression next.
                engine.judge = lambda *_: False
            elif result['canary']['reason'] == 'quality_failure':
                fallback = result['strategy'] == 'regex-inventory'
                break
        report = CanaryLearning(engine).report(actors['auditor'], trial)
        assert accepted == 1 and fallback
        assert report['phase'] == 'stopped'
        assert report['active_release'] == baseline['active_release']
        assert report['active_generation'] == 0
        return {'status': 'canary_fallback_verified', 'report': report,
                'scope': 'local real-file drill with weak baseline, fixed IDs and injected judge failure; '
                         'not independent performance evidence or a production deployment'}


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2, sort_keys=True))
