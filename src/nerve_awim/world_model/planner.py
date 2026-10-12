"""Bounded search over known transitions, with per-decision version pinning."""
from collections import deque
from .compiler import Simulator
from .contracts import digest, identifier


def plan(program, initial, allowed_actions, *, max_depth=5, max_nodes=100):
    if type(max_depth) is not int or not 1 <= max_depth <= 5 or type(max_nodes) is not int or not 1 <= max_nodes <= 100:
        raise ValueError('bounded planning limits required')
    if type(allowed_actions) is not list or not 1 <= len(allowed_actions) <= 16:
        raise ValueError('explicit bounded action allowlist required')
    for action in allowed_actions:
        identifier(action)
    sim = Simulator(program)
    queue = deque([(sim.initialise(initial),[])])
    seen, nodes, unknown = set(), 0, 0
    while queue:
        state, actions = queue.popleft()
        if sim.goal(state) is True:
            return {'status':'planned','actions':actions,'simulated_nodes':nodes,
                    'model_hash':digest(program),'initial_hash':digest(initial)}
        if len(actions) == max_depth:
            continue
        for action in allowed_actions:
            if nodes >= max_nodes:
                return {'status':'abstain','reason':'node_budget','actions':[],'simulated_nodes':nodes}
            nodes += 1
            next_state = sim.step(state,action)
            if sim.observe(next_state) is None or sim.goal(next_state) is None:
                unknown += 1
                continue
            key = digest(next_state)
            if key not in seen:
                seen.add(key)
                queue.append((next_state,actions+[action]))
    return {'status':'abstain','reason':'unknown_or_infeasible','actions':[],
            'simulated_nodes':nodes,'unknown_predictions':unknown}


def validate_dispatch(decision, program, observed, allowed_actions, remaining_actions):
    """Host must invoke immediately before each effect; no effects executed here."""
    if decision.get('status') != 'planned' or not decision.get('actions'):
        raise PermissionError('no known plan')
    if decision['model_hash'] != digest(program) or decision['initial_hash'] != digest(observed):
        raise PermissionError('stale model or observation; replan required')
    if remaining_actions < 1 or decision['actions'][0] not in allowed_actions:
        raise PermissionError('dispatch policy or action budget denied')
    return decision['actions'][0]
