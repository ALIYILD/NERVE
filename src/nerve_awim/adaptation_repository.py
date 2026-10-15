"""Read-only, evidence-checked adaptation on real repository source.

Uses the existing regex/AST tools and independent token-stream verifier.
No source is executed. The local operator's explicit command authorizes these
pure tools; it does not grant remote identity, model access or code modification.
"""
from pathlib import Path
import hashlib
import time
import sqlite3
import uuid
from .adaptation import AdaptationConfig, AdaptationCoordinator
from .arc_execution import ArcRuntime, ToolSpec, digest
from .agent_learning_v12 import RegisteredStrategy
from .governed_learning_v20 import GovernedLearning, LearningAuthority
from .repository_agents_v20 import regex_inventory, ast_inventory, token_inventory

TOOLS={'regex-inventory':regex_inventory,'ast-inventory':ast_inventory}
LEARNING_DOMAIN='repository-inventory-recovery-v1'
REVIEW_PROVENANCE='independent-token-recovery-v1'


def learned_recovery(c):
    """Only verified, reviewed recovery episodes can influence this pure tool route."""
    for memory in c['arc'].memories(c['actor'],domain=LEARNING_DOMAIN):
        if memory['provenance'] != REVIEW_PROVENANCE: continue
        record=c['arc'].inspect(c['actor'],memory['decision'])
        decision=record['decision']; outcome=record['outcome']
        if (decision['action']['registered_tool']=='ast-inventory' and
                decision['goal']=='top-level-function-inventory' and
                decision['parent_decision_id'] and outcome and
                outcome['semantic_status']=='verified'):
            parent=c['arc'].inspect(c['actor'],decision['parent_decision_id'])
            if (parent['decision']['action']['registered_tool']=='regex-inventory' and
                    parent['outcome'] and parent['outcome']['semantic_status']=='failed'):
                return memory['decision']
    return None


def repository_scope(root):
    """Stable local namespace; symlink aliases resolve to the same repository."""
    root=Path(root).resolve(strict=True)
    if not root.is_dir(): raise ValueError('repository directory required')
    return 'repository-'+hashlib.sha256(str(root).encode()).hexdigest()


def build_repository(path, *, mode='active-development', repository_root=None):
    scope=repository_scope(repository_root) if repository_root is not None else 'repository'
    agent='repository-adaptation' if repository_root is None else scope
    if repository_root is not None and Path(path).is_file():
        # Old records contain no root binding. Never infer ownership or bypass
        # an old agent-wide kill switch by silently moving into a new namespace.
        with sqlite3.connect(path) as con:
            tables={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for table in ('adaptation_tasks','adaptation_switch'):
                if table in tables and con.execute(f"SELECT 1 FROM {table} WHERE tenant=? AND agent=? LIMIT 1",('local-repository','repository-adaptation')).fetchone():
                    raise PermissionError('legacy repository state has no root binding; preserve it for review and use a new state directory')
    authority=LearningAuthority()
    actor=authority.issue('local-repository',agent,'runtime')
    operator=authority.issue('local-repository',agent,'operator')
    observed={}
    def validate(args):
        return (type(args) is dict and set(args)=={'source','file','content_hash'} and
                type(args['source']) is str and len(args['source'].encode())<=12000 and
                type(args['file']) is str and args['content_hash']==digest(args['source']))
    def verifier(value,args):
        return {'inventory':type(value) is list and value==token_inventory(args['source'])}
    def bind(args,refs):
        return any(r['reference_to_redacted_or_protected_content']=='sha256:'+digest(args['source']) for r in refs)
    strategies=[]
    for name,tool in TOOLS.items():
        def handler(args,tool=tool):
            value=tool(args['source']); observed['value']=value; return value
        strategies.append(RegisteredStrategy(name,name,handler))
    engine=GovernedLearning(path,authority=authority,strategies=strategies,judge=lambda task,value:verifier(value,task.payload)['inventory'],contract_revision='repository-task-adaptation-v1',baseline_routes={k:k for k in TOOLS})
    try: engine.status(operator)
    except LookupError: engine.bootstrap(operator)
    arc=ArcRuntime(engine,tools={name:ToolSpec(name,validate,verifier,evidence_bindings=bind) for name in TOOLS},mode='enforce')
    adaptation=AdaptationCoordinator(arc,AdaptationConfig(enabled=mode!='off',mode=mode))
    return dict(engine=engine,arc=arc,adaptation=adaptation,actor=actor,operator=operator,observed=observed,subject_scope=scope)


def run_sources(database, sources, *, policy='corrections', mode='active-development', restart=False, task_id=None, initial_tool='regex-inventory', repository_root=None, learn=False):
    """Sources are host-authorized (name,text) pairs. At most three files/task."""
    if initial_tool not in TOOLS: raise ValueError('registered initial tool required')
    if policy not in ('baseline','structured','corrections','strong-baseline'): raise ValueError('unknown policy')
    if not 1<=len(sources)<=3: raise ValueError('one to three source files per task')
    for name,source in sources:
        if type(name) is not str or type(source) is not str or len(source.encode())>12000: raise ValueError('bounded Python source required')
        # Parsing does not execute source; fail before dispatch if not valid Python.
        ast_inventory(source)
    c=build_repository(database,mode=mode,repository_root=repository_root); a=c['adaptation']; actor=c['actor']; task=task_id or 'repo-'+uuid.uuid4().hex
    active=mode=='active-development' and policy not in ('baseline','strong-baseline')
    if learn and (not active or policy!='corrections' or repository_root is None):
        raise ValueError('learning requires active corrections and an explicit repository root')
    if active:
        a.begin_task(actor,task_id=task,subject_scope=c['subject_scope'],goal_reference='top-level-function-inventory',constraints=['read-only','no-source-execution','independent-verification'])
        a.grant(c['operator'],task,c['operator'],subject_scope=c['subject_scope'],review_reference='local-operator-read-only-command')
    memory_id=learned_recovery(c) if learn else None
    attempts=[]; outputs=[]; correction_ids=[]; reused=0; probes=0; resumed=False; learned=[]
    for index,(name,source) in enumerate(sources):
        context=a.read_context(actor,task) if active else {'corrections':[]}
        applicable=[x for x in context['corrections'] if x['proposed_change']['field']=='recovery_tool']
        chosen='ast-inventory' if policy=='strong-baseline' else (applicable[-1]['proposed_change']['value'] if policy=='corrections' and applicable else initial_tool)
        # Guidance changes the proposal only; fresh evidence, dispatch gates and
        # the independent outcome verifier still run for every source.
        if memory_id: chosen='ast-inventory'
        reused+=int(index>0 and bool(applicable) and policy=='corrections')
        arguments={'source':source,'file':name,'content_hash':digest(source)}
        ref=a.snapshot(actor,task,'file-'+str(index),source) if active else c['arc'].snapshot(actor,task+':file-'+str(index),source)
        parent=None
        for attempt in range(2):
            decision=c['arc'].propose(actor,task,chosen,arguments,[ref],'top-level-function-inventory',['inventory'],parent_decision_id=parent,domain=LEARNING_DOMAIN if learn else 'nonclinical',concise_rationale=('Verified recovery guidance '+memory_id+'; fresh source requires independent verification' if memory_id else 'Host-authored evidence-linked decision summary'))
            before=time.perf_counter(); outcome=c['arc'].execute(actor,decision.decision_id)
            attempts.append({'file':name,'tool':chosen,'decision_id':decision.decision_id,'status':outcome.semantic_status,'names':list(c['observed'].get('value',[])),'seconds':time.perf_counter()-before,'evidence_digest':arguments['content_hash']})
            if outcome.semantic_status=='verified':
                if learn and parent and chosen=='ast-inventory':
                    c['arc'].review(c['operator'],decision.decision_id,label='accepted',provenance=REVIEW_PROVENANCE)
                    learned.append(decision.decision_id)
                outputs.append({'file':name,'functions':c['observed']['value'],'evidence_digest':arguments['content_hash']}); break
            if not active or policy!='corrections' or attempt==1 or chosen=='ast-inventory': break
            # A host deterministic review compares a pure alternative with a
            # separately implemented token-stream oracle. Count this probe.
            probes+=1
            if ast_inventory(source)!=token_inventory(source): break
            review=a.snapshot(actor,task,'review-'+str(index),{'source_digest':digest(source),'failed_decision':decision.decision_id,'reviewer':'independent-token-verifier','permitted_alternative':'ast-inventory'})
            cid=a.propose_correction(actor,task,failed_decision=decision.decision_id,kind='tool-recovery',proposed_change={'field':'recovery_tool','value':'ast-inventory'},evidence_reference=review)
            a.verify_correction(c['operator'],task,cid); correction_ids.append(cid)
            if restart and not resumed:
                cp=a.checkpoint(actor,task)
                c=build_repository(database,mode=mode,repository_root=repository_root);a=c['adaptation'];actor=c['actor']
                for principal in (actor,c['operator']): a.grant(c['operator'],task,principal,subject_scope=c['subject_scope'],review_reference='local-operator-reauthentication')
                a.resume(actor,task,cp)
                for old in correction_ids:a.verify_correction(c['operator'],task,old,reaffirm=True)
                resumed=True
            chosen=a.read_context(actor,task)['corrections'][-1]['proposed_change']['value'];parent=decision.decision_id
        if outcome.semantic_status!='verified': break
    success=len(outputs)==len(sources)
    if active:a.close_task(actor,task,status='completed' if success else 'review-required')
    state=a.inspect(actor,task) if active else {'status':'completed' if success else 'review-required','action_receipts':{}}
    return dict(task_id=task,repository_scope=c['subject_scope'],success=success,status=state['status'],attempts=attempts,outputs=outputs,corrections=len(correction_ids),correction_reuse=reused,review_probes=probes,resumed=resumed,receipt_count=len(state['action_receipts']),provider_calls=0,provider_cost_usd=0,source_executed=False,source_modified=False,mode=mode,policy=policy,initial_tool=initial_tool,learning_enabled=learn,learned_episode_ids=learned,memory_decision_id=memory_id,events=a.events(actor,task) if active else [])


def run_repository(database,root, *, paths=None, mode='active-development', restart=False, task_id=None, initial_tool='ast-inventory', learn=False):
    root=Path(root).resolve()
    if not root.is_dir(): raise ValueError('repository directory required')
    paths=paths or ['src/nerve_awim/arc_contracts.py','src/nerve_awim/repository_agents_v20.py']
    sources=[]
    for raw in paths:
        path=(root/raw).resolve()
        if root not in path.parents or path.suffix!='.py' or not path.is_file(): raise PermissionError('source must be a Python file inside the authorized repository')
        if path.stat().st_size>12000: raise ValueError('source exceeds 12KiB task limit')
        sources.append((str(path.relative_to(root)),path.read_text()))
    return run_sources(database,sources,mode=mode,restart=restart,task_id=task_id,initial_tool=initial_tool,repository_root=root,learn=learn)
