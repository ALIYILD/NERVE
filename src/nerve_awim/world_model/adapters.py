"""Host-only adapters to existing NERVE evidence, memory and research runtime."""
from .contracts import REVISION
from ..agentos_learning import expected_handoff


def observe_handoff(host, ledger, actor, *, profile, task, output, transition_id, episode):
    """Prediction receipt first; truth derives from existing host judge, not output."""
    ledger.reserve(actor,transition_id=transition_id,episode=episode,sequence=0,
                   action='handoff',previous={'pending':True},prediction=output,model=None)
    receipt = host.observe(profile,task,output,mode='world-model-offline')
    truth = expected_handoff(task)
    ledger.complete(actor,transition_id,outcome=truth,completion=truth['passed'])
    return {'host_receipt':receipt,'transition_id':transition_id,'deployment_authorized':False}


def propose_memory(memory, actor, model):
    """Semantic summary remains pending; retrieval rank is not model eligibility."""
    return memory.propose(actor,context='world-model-v1',kind='semantic',
        source_id=model['model_id'],content='Synthetic operational model '+model['model_id']+
        '; rulebook '+model['rulebook_hash']+'. Requires independent evaluation; not activation authority.')


def sensor_observation(runtime):
    """Read normalized simulated controller result; never controls a real device."""
    result = runtime.tick()
    if result.action is None:
        return {'status':'unavailable','prediction':None,'action':None,
                'environment_revision':'sensor-simulation-v1','deterministic_replay_eligible':False}
    return {'status':'simulated','prediction':None,'action':result.action,
            'environment_revision':'sensor-simulation-v1','deterministic_replay_eligible':False}


def shadow(program, episode, recommended_action):
    from .sandbox import execute
    rows = episode['transitions']
    predicted = execute(program,episode['initial'],[r['action'] for r in rows])
    actual_action = rows[0]['action'] if rows else None
    return {'observed_predictions':predicted,'recommended_action':recommended_action,
            'counterfactual_outcome':rows[0]['outcome'] if rows and recommended_action == actual_action else None,
            'counterfactual_status':'observed' if recommended_action == actual_action else 'unobserved',
            'external_actions':0}
