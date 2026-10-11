"""Actual NERVE source-file tasks with disjoint training and held-out files.

Measures routing among two existing, hand-written tools, not model learning.
All activation/rollback happens in a temporary research database. The operator
capability below is a simulated trusted host, not real human authentication.
"""
from hashlib import sha256
import json
from pathlib import Path
import tempfile

from nerve_awim.agent_learning_v12 import AgentTask
from nerve_awim.governed_learning_v20 import GovernedLearning, LearningAuthority
from nerve_awim.repository_agents_v20 import (
    CONTEXT, REPOSITORY_STRATEGIES, repository_judge, ast_inventory,
)

ROOT = Path(__file__).resolve().parents[1]
TRAIN_PATHS = (
    'src/nerve_awim/agent_learning_v12.py',
    'src/nerve_awim/agent_bridge_v13.py',
    'src/nerve_awim/core.py',
    'src/nerve_awim/evolution_v01.py',
)
HOLDOUT_PATHS = (
    'src/nerve_awim/recovery_learning_v17.py',
    'src/nerve_awim/memory_retrieval_v18.py',
    'src/nerve_awim/learn_v31.py',
    'src/nerve_awim/calibration_v15.py',
    'src/nerve_awim/autoresearch_v05.py',
    'src/nerve_awim/regression_v15.py',
    'src/nerve_awim/oidc_v27.py',
    'src/nerve_awim/parallel_agents_v11.py',
)


def load_tasks(paths):
    return [AgentTask(Path(path).stem, CONTEXT, (ROOT / path).read_text(encoding='utf-8'))
            for path in paths]


def benchmark():
    authority = LearningAuthority()
    actors = {role: authority.issue('public-repository', 'inventory-agent', role)
              for role in ('trainer', 'evaluator', 'operator', 'runtime')}
    with tempfile.TemporaryDirectory() as folder:
        engine = GovernedLearning(Path(folder) / 'outcomes.sqlite', authority=authority,
            strategies=REPOSITORY_STRATEGIES, judge=repository_judge,
            contract_revision='python-inventory-tools-and-token-judge-v2',
            baseline_routes={CONTEXT: 'regex-inventory'})
        baseline = engine.bootstrap(actors['operator'])
        for task in load_tasks(TRAIN_PATHS):
            engine.learn_from_task(actors['trainer'], task)
        candidate = engine.freeze_candidate(actors['trainer'])
        # The learner receives no holdout outcomes before the route is frozen.
        holdout = load_tasks(HOLDOUT_PATHS)
        evidence = engine.evaluate_candidate(actors['evaluator'], candidate, holdout)
        capable_hits = sum(repository_judge(t, ast_inventory(t.payload)) for t in holdout)
        before = engine.execute(actors['runtime'], holdout[0])
        activation = rollback = False
        if evidence['status'] == 'passed':
            active = engine.activate(actors['operator'], candidate,
                                     expected_generation=0, reason='demo-host-review')
            after = engine.execute(actors['runtime'], holdout[0])
            activation = after['release'] == active['active_release'] and after['strategy'] == 'ast-inventory'
            engine.rollback(actors['operator'], baseline['active_release'],
                            expected_generation=1, reason='demo-rollback-drill')
            reverted = engine.execute(actors['runtime'], holdout[0])
            rollback = reverted['release'] == before['release'] and reverted['value'] == before['value']
        manifest = {path: sha256((ROOT / path).read_bytes()).hexdigest()
                    for path in (*TRAIN_PATHS, *HOLDOUT_PATHS)}
        return {
            'task': 'inventory top-level functions in actual public NERVE Python files',
            'training_files': len(TRAIN_PATHS), 'heldout_files': len(HOLDOUT_PATHS),
            'evaluation': evidence,
            'capable_fixed_control': {'hits': capable_hits, 'tasks': len(holdout)},
            'approved_route_executed': activation,
            'rollback_restored_original_behaviour': rollback,
            'source_manifest_sha256': manifest,
            'scope': 'local temporary research runtime; simulated host operator approval',
            'limitations': 'Same-repository held-out files, small sample, two hand-written tools. '
                           'No live LLM, no general intelligence or clinical performance claim. '
                           'A capable fixed AST tool is the non-learning control.',
        }


if __name__ == '__main__':
    print(json.dumps(benchmark(), indent=2, sort_keys=True))
