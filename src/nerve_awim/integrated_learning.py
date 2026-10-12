"""One coupled offline research workflow across NERVE's six existing layers.

Creates disposable state only. Repository source is parsed, never executed or
modified. Symbolic rule induction and scripted Hermes calls are not weight updates
or evidence of general capability improvement.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import uuid

from .adaptation_repository import build_repository
from .arc_execution import digest
from .repository_agents_v20 import ast_inventory,token_inventory
from .uncertainty.ledger import Ledger
from .uncertainty.contracts import Claim
from .uncertainty.adapters import UncertaintyAdapter
from .uncertainty.world_model_adapter import WorldModelUncertainty
from .world_model.ledger import Ledger as WorldLedger,migrate
from .world_model.generalization import infer
from .world_model.compiler import compile_rules
from .world_model.registry import Registry
from .world_model.contracts import Policy as WorldPolicy
from .memory_v18 import MemoryAuthority,TrustedMemoryLedger
from .memory_gateway.gateway import MemoryGateway
from .memory_gateway.contracts import MemoryScope,MemoryRequest
from .hermes_agents import HermesAgentRuntime


class ScriptedProvider:
    """Explicit offline fixture using the real text-only Hermes runtime adapter."""
    calls=[]
    def __init__(self,**configuration):self.tools=[];self.configuration=configuration
    def run_conversation(self,message,**kwargs):
        payload=json.loads(message)
        if not payload.get('memory_context') or 'uncertainty' not in payload:raise ValueError('coupled memory and uncertainty context required')
        self.calls.append({'context_hash':digest(payload['memory_context']),'conflicts':payload['uncertainty']['open_conflict_ids']})
        return {'completed':True,'final_response':json.dumps({'conclusions':[{'claim_id':payload['claim_id']}]})}
    def close(self):pass


def _claim(ledger,actor,task,cid,value,content):
    source=ledger.register_source(actor,'source-'+cid,content,provenance='host-verification')
    claim=Claim(cid,actor.tenant,task,'repository-audit','inventory_verified',value,**source)
    ledger.add_claim(actor,claim)
    return claim


def _denied(callback):
    try:callback()
    except (PermissionError,RuntimeError):return True
    return False


def _cue(c,adapter,memory,reader,roles):
    from .cue_engine import Cue,ModelProfile
    from .cue_evaluation import DatasetManifest,ModelParity,Observation,PairedResult
    from .cue_learning import GovernedCueCoordinator
    coordinator=GovernedCueCoordinator(c['engine'],enabled=True,uncertainty=adapter)
    profile=ModelProfile('offline-fixture','integrated-scripted','v1','fixture-tokenizer','v1',('instruction',),'integrated-v1')
    cue=Cue('receipt-check',1,'Check the registered inventory verification receipt before answering.','instruction',profile.key,('research',),'integrated-fixture')
    manifest=DatasetManifest(('synthetic-discovery',),('synthetic-selection',),tuple('synthetic-check-'+str(i) for i in range(30)))
    model=ModelParity(profile.provider,profile.model,profile.revision,profile.tokenizer,profile.tokenizer_revision,'template','sampling',0.,128,'receipt-context',profile.key)
    candidate=coordinator.propose(roles['trainer'],cue,profile,'research',manifest,generator_id='fixture-proposer',model_config=model)
    pairs=tuple(PairedResult(Observation(t,model,True,True,.01,8,0.,t+'-baseline',True,'','baseline'),
                            Observation(t,model,True,True,.01,8,0.,t+'-candidate',True,cue.content_hash,'candidate')) for t in manifest.holdout)
    result=coordinator.evaluate(roles['evaluator'],candidate,pairs,evaluator_id='independent-fixture-checker')
    pending=coordinator.export_memory(roles['auditor'],candidate,memory,reader)
    if result['decision']['eligible']:raise AssertionError('synthetic no-gain cue must remain ineligible')
    return {'candidate_id':candidate,'decision':result['decision'],'synthetic_pairs':len(pairs),'pending_memory_id':pending,'pending_memory_status':memory.status(reader,pending).status,'activated':False},coordinator,profile


def run(repository,directory):
    root=Path(repository).resolve(strict=True)
    directory=Path(directory).resolve()
    if not root.is_dir():raise ValueError('repository directory required')
    if directory.exists():raise ValueError('fresh output directory required; previous evidence is never overwritten')
    paths=['src/nerve_awim/memory_gateway/contracts.py','src/nerve_awim/repository_agents_v20.py','src/nerve_awim/memory_gateway/null_kv_adapter.py']
    sources=[]
    for relative in paths:
        path=(root/relative).resolve(strict=True)
        if root not in path.parents or path.stat().st_size>12000:raise ValueError('bounded source inside repository required')
        source=path.read_text();ast_inventory(source);sources.append((relative,source))
    try:
        directory.mkdir(parents=True,exist_ok=False)
    except FileExistsError:
        raise ValueError('fresh output directory required; concurrent claim already exists') from None
    database=directory/'integrated.sqlite3'
    c=build_repository(database,repository_root=root);a=c['adaptation'];actor=c['actor'];operator=c['operator'];arc=c['arc']
    authority=c['engine'].authority
    roles={role:authority.issue(actor.tenant,actor.agent,role) for role in ('trainer','evaluator','auditor')}
    task='integrated-'+uuid.uuid4().hex
    a.begin_task(actor,task_id=task,subject_scope=c['subject_scope'],goal_reference='verified-repository-inventory',constraints=['read-only','independent-token-verification'])
    a.grant(operator,task,operator,subject_scope=c['subject_scope'],review_reference='local-research-review')
    migrate(database);world=WorldLedger(database,authority)
    receipts=[];correction_id=None;probe_receipt=None;reused_correction_id=None
    for index,(name,source) in enumerate(sources[:2]):
        ref=a.snapshot(actor,task,'training-'+str(index),source)
        args={'source':source,'file':name,'content_hash':digest(source)}
        if index==0:
            chosen='regex-inventory'
        else:
            selected_correction=a.read_context(actor,task)['corrections'][-1]
            chosen=selected_correction['proposed_change']['value']
            reused_correction_id=selected_correction['correction_id']
        decision=arc.propose(actor,task,chosen,args,[ref],'inventory',['inventory'])
        if index==0:
            outcome=arc.execute(actor,decision.decision_id)
            probe_receipt={'decision_id':decision.decision_id,'outcome_id':outcome.outcome_id,'tool':decision.action['registered_tool'],'verification':outcome.semantic_status}
            if outcome.semantic_status=='verified':raise AssertionError('explicit recovery probe must expose regex failure')
            if ast_inventory(source)!=token_inventory(source):raise AssertionError('independent AST alternative verification failed')
            review=a.snapshot(actor,task,'review',{'failed_decision':decision.decision_id,'source_hash':digest(source),'alternative':'ast-inventory','verifier':'token-stream'})
            correction_id=a.propose_correction(actor,task,failed_decision=decision.decision_id,kind='tool-recovery',proposed_change={'field':'recovery_tool','value':'ast-inventory'},evidence_reference=review)
            a.verify_correction(operator,task,correction_id)
            decision=arc.propose(actor,task,'ast-inventory',args,[ref],'inventory',['inventory'],parent_decision_id=decision.decision_id)
            # Reserve the predicted transition before the corresponding effect.
        before={'source_id':digest(source),'inventory_ready':False}
        episode='observed-inventory-'+str(index)
        world.episode(roles['trainer'],episode=episode,source=episode,family='repository-inventory',split='train',initial=before)
        tid=episode+'-transition'
        world.reserve(roles['trainer'],transition_id=tid,episode=episode,sequence=0,action='ast-inventory',previous=before,prediction={'source_id':digest(source),'inventory_ready':True},model='host-hypothesis')
        outcome=arc.execute(actor,decision.decision_id)
        if outcome.semantic_status!='verified':raise AssertionError('actual AST receipt must pass independent verification')
        world.complete(roles['trainer'],tid,outcome={'source_id':digest(source),'inventory_ready':True},completion=True)
        receipts.append({'decision_id':decision.decision_id,'outcome_id':outcome.outcome_id,'transition_id':tid,'source_path':name,'source_hash':digest(source),'names':c['observed']['value'],'verification':outcome.semantic_status})
    ledger=Ledger(c['engine'])
    supported=_claim(ledger,actor,task,'verified-training',True,{'receipts':receipts})
    adapter=UncertaintyAdapter(ledger,actor,task_id=task,dependency_claim_ids=[supported.claim_id])
    world_adapter=WorldModelUncertainty(ledger,world);world_adapter.enable(operator,mode='enforce')
    proposal=infer(world.episodes(roles['trainer']))
    if not proposal['rules']:raise AssertionError('two actual observed transitions must induce a bounded frame rule')
    for rule in proposal['rules']:world_adapter.bind_rule(operator,task_id=task,rule_id=rule['rule_id'],claim_ids=[supported.claim_id],review_ref='verified-arc-receipts')
    registry=Registry(world)
    model_id=registry.put(roles['trainer'],proposal['rules'],compile_rules(proposal['rules'],backend=proposal['backend']),WorldPolicy(enabled=True,model_backend='declarative-frame-v1'))
    registry.freeze(roles['evaluator'],model_id)
    third_name,third_source=sources[2]
    initial={'source_id':digest(third_source),'inventory_ready':False}
    plan=world_adapter.plan(roles['evaluator'],model_id,initial,['ast-inventory'])
    if plan['actions']!=['ast-inventory']:raise AssertionError('learned research plan unavailable')
    memory_authority=MemoryAuthority();memory=TrustedMemoryLedger(database,memory_authority)
    reader=memory_authority.issue(actor.tenant,actor.agent,permissions=('read','propose'))
    reviewer=memory_authority.issue(actor.tenant,actor.agent,permissions=('read','approve'))
    gateway=MemoryGateway(memory,uncertainty=adapter);scope=MemoryScope(actor.tenant,actor.agent,'integrated-inventory')
    memory_id=gateway.propose(reader,scope=scope,content='Verified AST inventory recovered from a failed regex inventory; two token-verified receipts support a bounded research transition. Model '+model_id+'.',source_id=model_id)
    gateway.decide(reviewer,memory_id,scope=scope,approve=True,evaluator_id='local-independent-token-review')
    retrieved=gateway.retrieve(reader,MemoryRequest(scope,'inventory'))
    cue_report,cue_coordinator,cue_profile=_cue(c,adapter,memory,reader,roles)
    scripted=type('IsolatedScriptedProvider',(ScriptedProvider,),{'calls':[]})
    hermes=HermesAgentRuntime(scripted,model='offline-scripted',provider='fixture',base_url='offline://no-network',enabled=True)
    def answer():
        current=gateway.retrieve(reader,MemoryRequest(scope,'inventory'))
        generated=hermes.execute('research',{'memory_context':current.context_text,'uncertainty':current.uncertainty,'claim_id':supported.claim_id},tenant=actor.tenant,agent=actor.agent)
        return adapter.final(generated['conclusions'])
    supported_output=answer()
    ref=a.snapshot(actor,task,'planned-third',third_source)
    queued=arc.propose(actor,task,'ast-inventory',{'source':third_source,'file':third_name,'content_hash':digest(third_source)},[ref],'inventory',['inventory'])
    assessment=adapter.policy.assess(actor,task,queued.decision_id,'ast-inventory',[supported.claim_id],impact='restricted',required=True)
    adapter.policy.bind(actor,queued.decision_id)
    _claim(ledger,actor,task,'synthetic-dispute',False,{'synthetic':True,'kind':'planted-audit-disagreement','not_a_repository_failure':True})
    conflict=ledger.detect(actor,task)[0]
    world_blocked=_denied(lambda:world_adapter.validate_dispatch(roles['evaluator'],plan,initial,['ast-inventory'],1))
    blocked_outcome=arc.execute(actor,queued.decision_id)
    arc_blocked=blocked_outcome.transport_status=='error' and blocked_outcome.semantic_status!='verified'
    qualified_output=answer()
    independent_task='independent-'+uuid.uuid4().hex
    independent=_claim(ledger,actor,independent_task,'independent-source',True,{'source':digest(third_source)})
    independent_ref=arc.snapshot(actor,independent_task,third_source)
    separate=arc.propose(actor,independent_task,'ast-inventory',{'source':third_source,'file':third_name,'content_hash':digest(third_source)},[independent_ref],'independent inventory',['inventory'])
    adapter.policy.assess(actor,independent_task,separate.decision_id,'ast-inventory',[independent.claim_id],impact='restricted',required=True)
    adapter.policy.bind(actor,separate.decision_id)
    independent_outcome=arc.execute(actor,separate.decision_id)
    wrong=memory_authority.issue('different-tenant',actor.agent,permissions=('read',))
    wrong_scope_denied=_denied(lambda:gateway.retrieve(wrong,MemoryRequest(scope,'inventory')))
    memory_omission_denied=_denied(lambda:MemoryGateway(memory).retrieve(reader,MemoryRequest(scope,'inventory')))
    from .world_model.planner import plan_registered
    from .world_model.contracts import REVISION
    bare_world=WorldLedger(database,authority)
    world_omission_denied=_denied(lambda:plan_registered(bare_world,roles['evaluator'],model_id,initial,['ast-inventory'],revision=REVISION,research_evaluation=True))
    restarted_ledger=Ledger(c['engine']);restarted_world=WorldModelUncertainty(restarted_ledger,WorldLedger(database,authority))
    restart_blocked=_denied(lambda:restarted_world.plan(roles['evaluator'],model_id,initial,['ast-inventory']))
    cue_conflict_blocked=_denied(lambda:cue_coordinator.select(actor,cue_profile,'research',permission_granted=True))
    cue_report['new_conflict_blocks_guidance']=cue_conflict_blocked
    final_memory=gateway.retrieve(reader,MemoryRequest(scope,'inventory'))
    report={'schema_version':'nerve-integrated-research-v1','task_id':task,'database':str(database),'repository':str(root),'scope':{'tenant':actor.tenant,'agent':actor.agent,'subject':c['subject_scope']},
        'evidence_mode':'actual read-only repository tools; scripted Hermes and cue observations; planted synthetic conflict',
        'arc_adaptation':{'receipts':receipts,'probe_receipt':probe_receipt,'regex_probe_failed':probe_receipt is not None and probe_receipt['verification']!='verified','reviewed_correction_id':correction_id,'reused_correction_id':reused_correction_id,'correction_reused':correction_id is not None and reused_correction_id==correction_id,'third_dispatch_blocked':arc_blocked,'unaffected_dispatch_verified':independent_outcome.semantic_status=='verified'},
        'world_model':{'model_id':model_id,'backend':proposal['backend'],'learned_rule_ids':[r['rule_id'] for r in proposal['rules']],'plan':plan,'new_conflict_blocked':world_blocked,'restart_blocked':restart_blocked,'omitted_adapter_denied':world_omission_denied,'eligibility':False},
        'uncertainty':{'conflict_id':conflict.conflict_id,'preserved_after_restart':conflict.conflict_id in [r.conflict_id for r in restarted_ledger.open_conflicts(actor,task)],'supported_output':supported_output,'qualified_output':qualified_output},
        'galahad_memory':{'approved_memory_id':memory_id,'retrieved_memory_ids':[r.memory_id for r in retrieved.records],'final_envelope':final_memory.uncertainty,'guidance_authority':False,'kv_status':'unverified-prefill-only','wrong_scope_denied':wrong_scope_denied,'omitted_adapter_denied':memory_omission_denied},
        'cce':cue_report,'hermes':{'scripted_fixture_calls':len(scripted.calls),'received_contexts':list(scripted.calls),'native_provider_calls':0},
        'implementation_hashes':{name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in ('integrated_learning.py','arc_execution.py','adaptation.py','world_model/generalization.py','world_model/planner.py','uncertainty/ledger.py','uncertainty/world_model_adapter.py','memory_gateway/gateway.py','cue_learning.py','hermes_agents.py')},
        'source_hashes':{name:digest(source) for name,source in sources},'source_hash_scheme':'sha256 of canonical JSON source string',
        'provider_calls':0,'provider_cost_usd':0,'source_executed':False,'source_modified':False,'deployment_authorized':False,'combined_improvement_claim':False,
        'limitations':['symbolic frame induction from two observations is not general model improvement','cue pairs are synthetic tied observations and cannot authorize promotion','memory is verified text prefill; no Galahad KV inference','planted disagreement exercises enforcement and does not establish a real repository defect']}
    checks=(report['arc_adaptation']['regex_probe_failed'],report['arc_adaptation']['correction_reused'],arc_blocked,world_blocked,restart_blocked,memory_omission_denied,world_omission_denied,wrong_scope_denied,cue_conflict_blocked,independent_outcome.semantic_status=='verified')
    report['status']='offline_verified' if all(checks) else 'failed'
    (directory/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository',required=True)
    parser.add_argument('--directory',required=True)
    args=parser.parse_args(argv)
    report=run(args.repository,args.directory)
    print(json.dumps(report,indent=2,sort_keys=True))
    return 0 if report['status']=='offline_verified' else 1

if __name__=='__main__':raise SystemExit(main())
