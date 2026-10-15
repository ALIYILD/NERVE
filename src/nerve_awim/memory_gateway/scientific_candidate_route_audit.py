"""Development-only routing audit; no model execution or efficacy comparison."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from . import scientific_candidate_screening as screening
from . import scientific_candidate_execution as execution
from . import scientific_task_bank as bank_module
from ..memory_v18 import MemoryAuthority
from .research_supervisor import _exclusive

VERSION='scientific-candidate-route-audit-v1'


def sources():
    pins=screening.sources();pins.update(bank_module.sources())
    for name in ('src/nerve_awim/memory_gateway/scientific_candidate_execution.py',
                 'src/nerve_awim/memory_gateway/scientific_candidate_route_audit.py',
                 'scripts/audit_scientific_candidate_routes.py'):
        pins[name]=sha256((screening.registration.importer.pilot.ROOT/name).read_bytes()).hexdigest()
    return pins


def run(directory,screen_directory,bank_directory,manifest_sha256):
    root,screen,bank_root=[Path(p).resolve() for p in (directory,screen_directory,bank_directory)]
    if len({root,screen,bank_root})!=3 or any(a in b.parents for a in (root,screen,bank_root) for b in (root,screen,bank_root) if a!=b):
        raise ValueError('separate_audit_directories_required')
    screening._private_directory(screen)
    path=screen/'report.json'
    with path.open('rb') as stream:raw=stream.read(4*1024*1024+1)
    if len(raw)>4*1024*1024:raise ValueError('bounded_screen_required')
    old=json.loads(raw)
    pins=sources()
    checked=screening.run(screen,old['registration_directory'],old['history_directory'])
    if screening.registration.importer.canonical(old)!=screening.registration.importer.canonical(checked):
        raise ValueError('screen_changed')
    if old['status']!='screened' or old['decision']['status']!='live':raise ValueError('live_screen_required')
    authority=MemoryAuthority()
    actor=authority.issue('synthetic-science','route-auditor',permissions=('read',))
    bank=bank_module.ScientificTaskBank(bank_root,authority,expected_manifest_hash=manifest_sha256,
        tenant_id='synthetic-science',generator_agent_id='route-auditor')
    # Never call status(): it intentionally validates both splits. Only development
    # access is authorized for this audit; no gate capability exists here.
    development=bank.development(actor)
    summaries=[]
    for proposal in old['decision']['allowed']:
        counts=Counter();strata={};traces=[];correct=0;incorrect=0
        for item in development:
            prepared=execution.prepare(proposal['candidate'],item['query'],item['evidence'])
            route=prepared['route'];counts[route]+=1
            strata.setdefault(item['stratum'],Counter())[route]+=1
            if route=='deterministic_conflict_abstention':
                if item['expected']['status']=='abstain':correct+=1
                else:incorrect+=1
            traces.append({'task_id':item['task_id'],'input_sha256':prepared['input_sha256'],
                           'route':route,'evidence_ids':prepared['evidence_ids']})
        summaries.append({'candidate_sha256':proposal['candidate_sha256'],
            'hypothesis_sha256':proposal['hypothesis_sha256'],'routes':dict(counts),
            'by_stratum':{key:dict(value) for key,value in strata.items()},
            'prestep_abstentions_agreeing_with_dev_answer':correct,
            'prestep_abstentions_disagreeing_with_dev_answer':incorrect,
            'route_trace_sha256':screening.registration.importer.digest(traces)})
    if sources()!=pins or path.read_bytes()!=raw or bank.development(actor)!=development:
        raise ValueError('audit_inputs_changed')
    if screening.run(screen,old['registration_directory'],old['history_directory'])!=old:
        raise ValueError('screen_changed')
    result={'version':VERSION,'status':'complete','source_sha256':pins,'screen_sha256':sha256(raw).hexdigest(),
        'manifest_sha256':manifest_sha256,'development_items':len(development),'candidates':summaries,
        'model_calls':0,'model_predictions':0,'holdout_accessed':False,'efficacy_established':False,
        'promotion_authorized':False,'scope':'Development routing audit only; model routes were not executed.'}
    screening._private_directory(root,create=True)
    with _exclusive(root):screening.registration.importer._save_exact(root/'report.json',result)
    return result
