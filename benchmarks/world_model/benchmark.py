"""Matched, disjoint-parameter synthetic ablations; no provider calls.

Run PYTHONPATH=src python benchmarks/world_model/benchmark.py.
Final task parameters never enter the proposer. The exact-state model is expected
to abstain on new parameters; this is a useful negative generalization result.
"""
import json
import time
from nerve_awim.world_model.compiler import compile_rules
from nerve_awim.world_model.contracts import Rule, digest
from nerve_awim.world_model.planner import plan

FAMILIES = {'workflow':('prepare','validate','finish'),
            'retry_api':('request','refresh','retry'),
            'data_transform':('parse','normalize','export')}


def state(family,parameter,stage):
    return {'family':family,'parameter':parameter,'stage':stage}


def host_run(family,parameter,actions):
    stage=0
    for action in actions:
        if stage < 3 and action == FAMILIES[family][stage]:
            stage+=1
    return stage == 3


def run():
    started=time.monotonic()
    rules=[]
    for family,actions in FAMILIES.items():
        for parameter in range(2):
            for stage,action in enumerate(actions):
                rid=f'{family}_{parameter}_{stage}'
                rules.append(Rule(rid,1,family,state(family,parameter,stage),action,
                    state(family,parameter,stage+1),stage == 2,[rid],[],status='supported').to_dict())
    program=compile_rules(rules)
    reports={}
    for variant in ('baseline','replay_only','rulebook_replay','bounded_population','retained_memory'):
        rows=[]
        for split,parameters in (('selection',range(10,14)),('final',range(100,108)),('retention',range(2))):
            for family,actions in FAMILIES.items():
                for parameter in parameters:
                    if variant == 'baseline':
                        decision={'actions':[actions[-1]],'status':'planned','simulated_nodes':0}
                    else:
                        decision=plan(program,state(family,parameter,0),list(actions))
                    success=host_run(family,parameter,decision['actions'])
                    rows.append({'split':split,'family':family,'parameter':parameter,'success':success,
                                 'abstained':decision['status']=='abstain','simulated_nodes':decision['simulated_nodes'],
                                 'simulator_actions':len(decision['actions']),'real_actions':0,
                                 'llm_calls':0,'tokens':0,'provider_cost':0,'policy_violations':0})
        reports[variant]={'episodes':len(rows),'success':sum(r['success'] for r in rows),
                          'abstained':sum(r['abstained'] for r in rows),'rows':rows}
    return {'evidence_mode':'offline deterministic simulator','status':'no_independent_final_gain',
            'reports':reports,'training_manifest_hash':digest(rules),'wall_seconds':time.monotonic()-started,
            'limitations':['exact-state lookup cannot generalize to unseen parameters',
                          'rulebook, population and retained-memory variants share identical compiled behavior',
                          'ablation effects therefore unestablished; no statistical or deployment claim'],
            'deployment_authorized':False}


if __name__ == '__main__':
    print(json.dumps(run(),indent=2))
