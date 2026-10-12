"""NERVE model-guided research evaluation of existing read-only repository tools.

Only fixed registered inventory/verification/handoff operations are available.
Source files are never executed or modified. Derived artifacts live in the study
folder. This evaluates a candidate; it does not activate a production release.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from .contracts import Policy, digest, IntegrityError
from .ledger import Ledger, migrate
from .generalization import infer, FRAME_BACKEND
from .compiler import compile_rules
from .registry import Registry
from .planner import plan_registered, validate_dispatch
from .replay import replay
from .fidelity import assess
from ..governed_learning_v20 import LearningAuthority
from ..repository_pilot_v22 import file_task
from ..repository_agents_v20 import ast_inventory, token_inventory
from ..agentos_learning import AgentOSLearning, atomic_json, expected_handoff

ACTIONS=['inventory','verify','handoff']
TRAIN_FILES=['src/nerve_awim/repository_agents_v20.py','src/nerve_awim/improvement_loop.py']
FINAL_FILES=['src/nerve_awim/host_lease.py','src/nerve_awim/hermes_learning.py',
             'src/nerve_awim/worldcore_v20.py','src/nerve_awim/observed_runtime_v29.py',
             'src/nerve_awim/runtime_v28.py','src/nerve_awim/learn_mcp.py']


class RepositoryEpisode:
    def __init__(self, root, relative, directory, handoff_host):
        self.root,self.relative=Path(root),relative
        self.task=file_task(root,relative)
        self.artifact=Path(directory)/(self.task.task_id+'.json')
        self.host=handoff_host
        self.state={'source_id':self.task.task_id,'stage':0,'artifact_exists':False,'verified':False,'complete':False}
        self.calls=0

    def step(self, action):
        if action not in ACTIONS:
            raise PermissionError('only registered read-only research actions allowed')
        if file_task(self.root,self.relative).task_id != self.task.task_id:
            raise IntegrityError('repository source changed; invalidate plan')
        self.calls+=1
        if action == 'inventory' and self.state['stage'] == 0:
            names=ast_inventory(self.task.payload)
            atomic_json(self.artifact,{'source_id':self.task.task_id,'names':names})
            self.state.update(stage=1,artifact_exists=self.artifact.is_file())
        elif action == 'verify' and self.state['stage'] == 1:
            artifact=json.loads(self.artifact.read_text())
            valid=artifact == {'source_id':self.task.task_id,'names':token_inventory(self.task.payload)}
            self.state.update(stage=2 if valid else 1,verified=valid)
        elif action == 'handoff':
            # Recheck evidence immediately before claiming task completion.
            exists=self.artifact.is_file()
            valid=exists and json.loads(self.artifact.read_text()) == {'source_id':self.task.task_id,'names':token_inventory(self.task.payload)}
            evidence={'id':self.task.task_id,'exit_code':0 if valid else 1,
                      'artifact_exists':exists,'qa_passed':valid and self.state['verified'],'memory_written':False}
            truth=expected_handoff(evidence)
            self.host.observe('repository-model-study',evidence,truth,mode='world-model-offline')
            if truth['passed']:
                self.state.update(stage=3,complete=True)
        return deepcopy(self.state),self.state['complete']


def run_repository_study(root,directory):
    root=Path(root).resolve(strict=True)
    directory=Path(directory)
    if directory.exists():
        raise ValueError('fresh repository study directory required')
    # Pin all source snapshots and ensure no renamed byte-identical holdout source.
    manifests={name:file_task(root,name) for name in TRAIN_FILES+FINAL_FILES}
    ids=[t.task_id for t in manifests.values()]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate source content across study partitions')
    directory.mkdir(parents=True)
    path=directory/'world-model.sqlite3'
    migrate(path)
    authority=LearningAuthority()
    trainer=authority.issue('offline','repository-study','trainer')
    evaluator=authority.issue('offline','repository-study','evaluator')
    ledger=Ledger(path,authority)
    host=AgentOSLearning(directory/'handoff')
    scope=ledger.scope(evaluator,'evaluator')
    with ledger.db() as db:
        for name in FINAL_FILES:
            db.execute('INSERT INTO wm_final VALUES(?,?,?,?,0)',(scope,manifests[name].task_id,'repository_study',None))
    for number,name in enumerate(TRAIN_FILES):
        episode=RepositoryEpisode(root,name,directory/'train',host)
        eid=f'train_{number}'
        ledger.episode(trainer,episode=eid,source=manifests[name].task_id,family='repository_inventory',split='train',initial=episode.state)
        for i,action in enumerate(ACTIONS):
            tid=f'{eid}_{i}'
            ledger.reserve(trainer,transition_id=tid,episode=eid,sequence=i,action=action,previous=episode.state,
                           prediction={**episode.state,'stage':3,'complete':True},model='premature_handoff')
            outcome,done=episode.step(action)
            ledger.complete(trainer,tid,outcome=outcome,completion=done)
    rules=infer(ledger.episodes(trainer))['rules']
    program=compile_rules(rules,backend=FRAME_BACKEND)
    registry=Registry(ledger)
    model=registry.put(trainer,rules,program,Policy(enabled=True,model_backend=FRAME_BACKEND))
    replay_report=replay(program,ledger.episodes(trainer))
    fidelity=assess(rules,program)
    if not replay_report['replay_pass'] or fidelity['status'] != 'pass':
        raise ValueError('candidate failed required verification')
    registry.freeze(evaluator,model)
    with ledger.db() as db:
        db.execute('UPDATE wm_final SET model=?,consumed=1 WHERE scope=?',(model,scope))
    rows=[]
    for number,name in enumerate(FINAL_FILES):
        if file_task(root,name).task_id != manifests[name].task_id:
            raise IntegrityError('pinned holdout source drift')
        baseline=RepositoryEpisode(root,name,directory/'baseline',host)
        baseline.step('handoff')
        candidate=RepositoryEpisode(root,name,directory/'candidate',host)
        nodes=0
        for _ in range(3):
            decision=plan_registered(ledger,evaluator,model,candidate.state,ACTIONS,
                                     revision='normalized-workflow-v1',research_evaluation=True)
            nodes+=decision['simulated_nodes']
            if decision['status'] != 'planned':
                break
            action=validate_dispatch(decision,program,candidate.state,ACTIONS,3-candidate.calls)
            candidate.step(action)
        rows.append({'path':name,'source_id':candidate.task.task_id,'baseline_success':baseline.state['complete'],
                     'candidate_success':candidate.state['complete'],'read_only_tool_calls':candidate.calls,
                     'simulated_nodes':nodes,'artifact':str(candidate.artifact)})
    report={'evidence_mode':'real local read-only repository tools; deterministic learned workflow',
            'model_id':model,'tasks':len(rows),'baseline_success':sum(r['baseline_success'] for r in rows),
            'candidate_success':sum(r['candidate_success'] for r in rows),'results':rows,
            'replay':replay_report,'fidelity':fidelity,'holdout_status':'consumed',
            'source_files_modified':False,'provider_calls':0,'deployment_authorized':False,'eligibility':False,
            'limitations':['learned inventory/verify/handoff order, not code repair or general software intelligence',
                          'small curated local source sample; no statistical generalization claim',
                          'trusted research host restricts all actions; no production model activation']}
    atomic_json(directory/'report.json',report)
    return report
