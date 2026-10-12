"""Read-only, evidence-checked adaptation on real repository source.

Uses the existing regex/AST tools and independent token-stream verifier.
No source is executed. The local operator's explicit command authorizes these
pure tools; it does not grant remote identity, model access or code modification.
"""
from pathlib import Path
import hashlib
import time
import uuid
from .adaptation import AdaptationConfig, AdaptationCoordinator
from .arc_execution import ArcRuntime, ToolSpec, digest
from .agent_learning_v12 import RegisteredStrategy
from .governed_learning_v20 import GovernedLearning, LearningAuthority
from .repository_agents_v20 import regex_inventory, ast_inventory, token_inventory

TOOLS={'regex-inventory':regex_inventory,'ast-inventory':ast_inventory}


def build_repository(path, *, mode='active-development'):
    authority=LearningAuthority()
    actor=authority.issue('local-repository','repository-adaptation','runtime')
    operator=authority.issue('local-repository','repository-adaptation','operator')
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
    return dict(engine=engine,arc=arc,adaptation=adaptation,actor=actor,operator=operator,observed=observed)


def run_sources(database, sources, *, policy='corrections', mode='active-development', restart=False, task_id=None, initial_tool='regex-inventory'):
    """Sources are host-authorized (name,text) pairs. At most three files/task."""
    if initial_tool not in TOOLS: raise ValueError('registered initial tool required')
    if policy not in ('baseline','structured','corrections','strong-baseline'): raise ValueError('unknown policy')
    if not 1<=len(sources)<=3: raise ValueError('one to three source files per task')
    for name,source in sources:
        if type(name) is not str or type(source) is not str or len(source.encode())>12000: raise ValueError('bounded Python source required')
        # Parsing does not execute source; fail before dispatch if not valid Python.
        ast_inventory(source)
    c=build_repository(database,mode=mode); a=c['adaptation']; actor=c['actor']; task=task_id or 'repo-'+uuid.uuid4().hex
    active=mode=='active-development' and policy not in ('baseline','strong-baseline')
    if active:
        a.begin_task(actor,task_id=task,subject_scope='repository',goal_reference='top-level-function-inventory',constraints=['read-only','no-source-execution','independent-verification'])
        a.grant(c['operator'],task,c['operator'],subject_scope='repository',review_reference='local-operator-read-only-command')
    attempts=[]; outputs=[]; correction_ids=[]; reused=0; probes=0; resumed=False
    for index,(name,source) in enumerate(sources):
        context=a.read_context(actor,task) if active else {'corrections':[]}
        applicable=[x for x in context['corrections'] if x['proposed_change']['field']=='recovery_tool']
        chosen='ast-inventory' if policy=='strong-baseline' else (applicable[-1]['proposed_change']['value'] if policy=='corrections' and applicable else initial_tool)
        reused+=int(index>0 and bool(applicable) and policy=='corrections')
        arguments={'source':source,'file':name,'content_hash':digest(source)}
        ref=a.snapshot(actor,task,'file-'+str(index),source) if active else c['arc'].snapshot(actor,task+':file-'+str(index),source)
        parent=None
        for attempt in range(2):
            decision=c['arc'].propose(actor,task,chosen,arguments,[ref],'top-level-function-inventory',['inventory'],parent_decision_id=parent)
            before=time.perf_counter(); outcome=c['arc'].execute(actor,decision.decision_id)
            attempts.append({'file':name,'tool':chosen,'decision_id':decision.decision_id,'status':outcome.semantic_status,'names':list(c['observed'].get('value',[])),'seconds':time.perf_counter()-before,'evidence_digest':arguments['content_hash']})
            if outcome.semantic_status=='verified':
                outputs.append({'file':name,'functions':c['observed']['value'],'evidence_digest':arguments['content_hash']}); break
            if not active or policy!='corrections' or attempt==1: break
            # A host deterministic review compares a pure alternative with a
            # separately implemented token-stream oracle. Count this probe.
            probes+=1
            if ast_inventory(source)!=token_inventory(source): break
            review=a.snapshot(actor,task,'review-'+str(index),{'source_digest':digest(source),'failed_decision':decision.decision_id,'reviewer':'independent-token-verifier','permitted_alternative':'ast-inventory'})
            cid=a.propose_correction(actor,task,failed_decision=decision.decision_id,kind='tool-recovery',proposed_change={'field':'recovery_tool','value':'ast-inventory'},evidence_reference=review)
            a.verify_correction(c['operator'],task,cid); correction_ids.append(cid)
            if restart and not resumed:
                cp=a.checkpoint(actor,task)
                c=build_repository(database,mode=mode);a=c['adaptation'];actor=c['actor']
                for principal in (actor,c['operator']): a.grant(c['operator'],task,principal,subject_scope='repository',review_reference='local-operator-reauthentication')
                a.resume(actor,task,cp)
                for old in correction_ids:a.verify_correction(c['operator'],task,old,reaffirm=True)
                resumed=True
            chosen=a.read_context(actor,task)['corrections'][-1]['proposed_change']['value'];parent=decision.decision_id
        if outcome.semantic_status!='verified': break
    success=len(outputs)==len(sources)
    if active:a.close_task(actor,task,status='completed' if success else 'review-required')
    state=a.inspect(actor,task) if active else {'status':'completed' if success else 'review-required','action_receipts':{}}
    return dict(task_id=task,success=success,status=state['status'],attempts=attempts,outputs=outputs,corrections=len(correction_ids),correction_reuse=reused,review_probes=probes,resumed=resumed,receipt_count=len(state['action_receipts']),provider_calls=0,provider_cost_usd=0,source_executed=False,source_modified=False,mode=mode,policy=policy,initial_tool=initial_tool,events=a.events(actor,task) if active else [])


def run_repository(database,root, *, paths=None, mode='active-development', restart=False, task_id=None, initial_tool='ast-inventory'):
    root=Path(root).resolve()
    if not root.is_dir(): raise ValueError('repository directory required')
    paths=paths or ['src/nerve_awim/arc_contracts.py','src/nerve_awim/repository_agents_v20.py']
    sources=[]
    for raw in paths:
        path=(root/raw).resolve()
        if root not in path.parents or path.suffix!='.py' or not path.is_file(): raise PermissionError('source must be a Python file inside the authorized repository')
        if path.stat().st_size>12000: raise ValueError('source exceeds 12KiB task limit')
        sources.append((str(path.relative_to(root)),path.read_text()))
    return run_sources(database,sources,mode=mode,restart=restart,task_id=task_id,initial_tool=initial_tool)
