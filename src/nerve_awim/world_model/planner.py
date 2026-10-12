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


def plan_registered(ledger, actor, model_id, initial, allowed_actions, *, revision,
                    research_evaluation=False, max_depth=5, max_nodes=100):
    """Model lookup and authority checks precede planning at the host boundary.

    Evaluators may exercise frozen candidates for bounded research. A runtime
    actor needs an eligible artifact; a caller boolean cannot grant that role.
    No source/path/text memory can bypass registry integrity or revision checks.
    """
    from .registry import Registry
    if research_evaluation:
        ledger.scope(actor,'evaluator')
    else:
        ledger.scope(actor,'runtime')
    model=Registry(ledger).get(actor,model_id)
    required=('frozen','eligible') if research_evaluation else ('eligible',)
    if model['state'] not in required or 'dependencies' not in model:
        raise PermissionError('verified frozen research model or eligible runtime model required')
    if revision != model['environment_revision']:
        raise PermissionError('environment revision drift; revalidation required')
    from .contracts import Policy
    pinned=Policy.load(model['evaluation_policy'])
    decision=plan(model['program'],initial,allowed_actions,
                  max_depth=min(max_depth,pinned.max_plan_depth),
                  max_nodes=min(max_nodes,pinned.max_simulated_nodes_per_decision))
    return {**decision,'model_id':model_id,'environment_revision':revision,
            'research_evaluation':research_evaluation,'deployment_authorized':False}
