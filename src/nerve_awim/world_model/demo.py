"""Synthetic observed workflow fixture. No provider or production authority."""
from copy import deepcopy
from .contracts import Policy
from .ledger import Ledger,migrate
from .coordinator import Coordinator
from .registry import Registry
from .replay import replay
from .fidelity import assess
from .adapters import shadow
from ..governed_learning_v20 import LearningAuthority


def host_step(state, action):
    # Fixture owns truth; scripted proposer sees only recorded transitions.
    stage = state['stage']
    next_stage = stage+1 if (stage,action) in ((0,'prepare'),(1,'validate'),(2,'finish')) else stage
    return {'stage':next_stage}, next_stage == 3


def populate(ledger, trainer, evaluator):
    for split in ('train','selection','regression','final'):
        actor = trainer if split == 'train' else evaluator
        episode = split+'_workflow'
        ledger.episode(actor,episode=episode,source=split+'_source',family='workflow',split=split,initial={'stage':0})
        state = {'stage':0}
        # Selection/final are different episodes, but share mechanics/states: no
        # claim of independently generated tasks or generalization from these.
        for i,action in enumerate(('prepare','validate','finish')):
            tid = episode+'_'+str(i)
            ledger.reserve(actor,transition_id=tid,episode=episode,sequence=i,action=action,
                           previous=state,prediction={'stage':3},model='baseline')
            state,goal = host_step(state,action)
            ledger.complete(actor,tid,outcome=state,completion=goal)


def run_demo(path):
    migrate(path)
    authority = LearningAuthority()
    trainer = authority.issue('offline','demo','trainer')
    evaluator = authority.issue('offline','demo','evaluator')
    ledger = Ledger(path,authority)
    populate(ledger,trainer,evaluator)
    policy = Policy(enabled=True)
    coordinator = Coordinator(ledger,trainer=trainer,evaluator=evaluator,policy=policy)
    run_id = coordinator.create()
    first = coordinator.resume(run_id,stop_after='compile')
    # New service and DB connection reconstruct the checkpoint instead of resetting budgets.
    restarted = Coordinator(Ledger(path,authority),trainer=trainer,evaluator=evaluator,policy=policy)
    result = restarted.resume(run_id)
    model = Registry(ledger).get(evaluator,result['body']['model_id'])
    bad = deepcopy(model['program'])
    bad['entries'][0]['after'] = {'stage':99}
    from .release import SimulatedRelease
    operator = authority.issue('offline','demo','operator')
    runtime = authority.issue('offline','demo','runtime')
    registry = Registry(ledger)
    simulated_successor = registry.put(trainer,model['rules'],model['program'],policy,parent=model['model_id'])
    registry.freeze(evaluator,simulated_successor)
    release = SimulatedRelease(ledger)
    config = {'max_depth':5,'max_nodes':100}
    release.authorize(operator,model['model_id'],expected_generation=0,planner_config=config,reason='isolated synthetic baseline')
    release.authorize(operator,simulated_successor,expected_generation=1,planner_config=config,reason='isolated synthetic canary')
    rollback = release.monitor(runtime,expected_generation=2,observed_ok=False,elapsed_ms=1)
    rollback['recovered_release'] = SimulatedRelease(Ledger(path,authority)).status(operator)
    return {'run_id':run_id,'model_id':model['model_id'],'status':result['body']['stop_reason'],
            'eligibility':False,'deployment_authorized':False,
            'evidence_mode':'scripted offline proposer','provider_calls':0,'provider_cost':0,
            'restart_budget_before':first['budget'],'restart_budget_after':result['budget'],
            'bad_candidate_replay':replay(bad,ledger.episodes(trainer)),
            'bad_candidate_fidelity':assess(model['rules'],bad),
            'reports':result['body']['reports'],'simulated_rollback':rollback,
            'shadow':shadow(model['program'],ledger.episodes(trainer)[0],'finish'),
            'limitations':['shared synthetic mechanics; independent task gain not established',
                           'no live provider, arbitrary Python, or canary/promotion authorization']}
