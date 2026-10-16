#!/usr/bin/env python3
"""Versioned aggregate-only L5 registration; old sixteen-item CLIs stay unchanged."""
import argparse
import ast
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from nerve_awim.memory_gateway.scientific_negative_evidence import NegativeEvidenceJournal
from nerve_awim.memory_gateway.scientific_episode_import import SCOPE

VERSION='family-b-aggregate-registration-v1'
ROOT=Path(__file__).resolve().parents[1]
CANONICAL_HISTORY=Path('/Users/aliyildirim/nerve-research-runs/scientific-negative-history-v1/rejections.sqlite')
SEAMS={'abstention-rule','extraction-schema','prompt-fragment'}
IMPORTS={'copy','decimal','nerve_awim.memory_gateway.scientific_family_b_adapter'}
FORBIDDEN={'open','exec','eval','compile','__import__','getattr','setattr','delattr','globals','locals','vars','input','breakpoint'}


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(value):return sha256(canonical(value).encode()).hexdigest()
def filehash(path):return sha256(Path(path).read_bytes()).hexdigest()


def clusters(aggregate):
    if not aggregate['complete'] or aggregate['kind']!='dev' or aggregate['verdict']!='exploratory_failures':
        raise ValueError('completed_failure_supported_L4_required')
    tables=aggregate['tables']['adapted_v1']
    if len(tables)!=9 or any(v['n']!=100 for v in tables.values()):raise ValueError('nine_complete_strata_required')
    result=[]
    for stratum,t in sorted(tables.items()):
        failures=t['n']-t['correct']
        if sum(t['diagnoses'].values())!=failures:raise ValueError('diagnosis_counts_changed')
        for label,count in sorted(t['diagnoses'].items()):
            if type(count) is not int or count<=0:raise ValueError('positive_failure_count_required')
            result.append({'stratum':stratum,'diagnosis':label,'count':count})
    return sorted(result,key=lambda x:(-x['count'],x['stratum'],x['diagnosis']))


def static_check(path,seam,fragment):
    if seam not in SEAMS or not isinstance(fragment,str) or len(fragment)>400:raise ValueError('allowed_seam_fragment_required')
    raw=Path(path).read_bytes()
    if not 1<=len(raw)<=8000:raise ValueError('candidate_size_cap')
    tree=ast.parse(raw)
    if not any(isinstance(n,ast.FunctionDef) and n.name=='prepare' for n in tree.body):raise ValueError('prepare_required')
    for n in ast.walk(tree):
        if isinstance(n,ast.Import):
            if any(a.name not in IMPORTS for a in n.names):raise ValueError('import_not_allowed')
        if isinstance(n,ast.ImportFrom):
            names={str(n.module)+'.'+a.name for a in n.names}
            if n.level or n.module not in IMPORTS and not names<=IMPORTS:raise ValueError('import_not_allowed')
        if isinstance(n,ast.Name) and (n.id in FORBIDDEN or n.id.startswith('__')):raise ValueError('unsafe_name')
        if isinstance(n,ast.Attribute) and n.attr.startswith('__'):raise ValueError('unsafe_attribute')
        if isinstance(n,(ast.Global,ast.Nonlocal,ast.ClassDef,ast.AsyncFunctionDef)):raise ValueError('unsupported_candidate_construct')
    return {'source_sha256':sha256(raw).hexdigest(),'normalized_ast_sha256':sha256(ast.dump(tree,include_attributes=False).encode()).hexdigest(),'bytes':len(raw),'seam':seam,'fragment_characters':len(fragment),'review_required':'Static screening does not prove semantic seam confinement; independent source review required before study.'}


def history_snapshot(path):
    path=Path(path).resolve();before=filehash(path)
    journal=NegativeEvidenceJournal(path,None,SCOPE,None)
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        rows,head=journal._validate(db)
    if filehash(path)!=before:raise ValueError('negative_history_changed')
    return {'sha256':before,'head':head,'count':len(rows)},rows


def register(study,proposals,history,directory):
    # Replay reads private receipts internally, but only aggregate counts enter episodes or design.
    import run_scientific_family_b_canada as harness
    from unittest.mock import patch
    with patch.object(harness.transport,'network',side_effect=AssertionError('L5 cannot perform inference')):
        aggregate=harness.verify(Path(study))
    registration=harness.read(Path(study)/'registration.json')
    if registration['candidate_module'] is not None:raise ValueError('L4_baseline_required')
    groups=clusters(aggregate)
    if not 1<=len(proposals)<=3:raise ValueError('one_to_three_proposals_required')
    if Path(history).resolve()!=CANONICAL_HISTORY:raise ValueError('canonical_negative_history_required')
    history_info,rejected=history_snapshot(history)
    history_info.update(path=str(CANONICAL_HISTORY),scope='synthetic-science/model-research/episodes',authority_reference='docs/galahad/67-negative-evidence-screening.md',limitation='Zero canonical journal records is not a claim that no prior study/document reports negative findings; actual candidate review must screen prior documented hypotheses too.')
    result=[]
    for p in proposals:
        if set(p)!={'id','module','seam','fragment','hypothesis','predicted_regression_stratum','cluster','selected'}:raise ValueError('exact_proposal_schema_required')
        if p['cluster'] not in groups or type(p['selected']) is not bool:raise ValueError('observed_cluster_required')
        if not p['hypothesis'] or p['predicted_regression_stratum'] not in aggregate['tables']['adapted_v1']:raise ValueError('hypothesis_and_regression_required')
        module=Path(p['module'])
        if module.is_absolute() or '..' in module.parts or not str(module).startswith('src/nerve_awim/memory_gateway/'):raise ValueError('candidate_module_path_required')
        check=static_check(ROOT/module,p['seam'],p['fragment'])
        if any(r['proposal']['candidate_sha256']==check['source_sha256'] for r in rejected):raise ValueError('previously_rejected_candidate')
        # Historical typed-config distance is not defined for arbitrary source patches.
        # Fail closed rather than silently treating an incomparable rejection as novel.
        if rejected:raise ValueError('nonempty_legacy_history_requires_comparable_versioned_screen')
        result.append(dict(p,static=check,hypothesis_sha256=digest(p),status='selected' if p['selected'] else 'archived'))
    selected=[p for p in result if p['selected']]
    if len(selected)!=1 or selected[0]['cluster']['count']!=groups[0]['count']:raise ValueError('select_one_largest_cluster_required')
    if len({p['id'] for p in result})!=len(result) or len({p['static']['normalized_ast_sha256'] for p in result})!=len(result):raise ValueError('duplicate_proposals')
    root=Path(directory);root.mkdir(mode=0o700)
    receipt_sha=filehash(Path(study)/'aggregate.json');head='0'*64;episodes=[]
    for i,g in enumerate(groups):
        e={'version':'family-b-aggregate-episode-v1','ordinal':i,'source_receipt_sha256':receipt_sha,'candidate_id':'adapted_v1',**g,'synthetic_only':True,'item_level':False}
        payload=digest(e);chain=digest([i,head,payload]);episodes.append({'episode':e,'payload_sha256':payload,'previous':head,'chain':chain});head=chain
    report={'version':VERSION,'wrapper_sha256':filehash(__file__),'proposal_payload_sha256':digest(proposals),'created_at_utc':datetime.now(timezone.utc).isoformat(),'aggregate_sha256':receipt_sha,'registration_sha256':filehash(Path(study)/'registration.json'),'episode_head':head,'episodes':episodes,'proposals':result,'negative_history':history_info,'history_comparison':'Existing journal verified read-only; zero records means no rejected hash/near-duplicate can match. Nonempty legacy typed-config history fails closed.','new_model_calls':0,'holdout_accessed':False,'promotion_authorized':False,'compatibility':'Separate aggregate episode journal; original ExperienceStoreV2 supports only four format-probe ordinals and is not silently reused.'}
    target=root/'registration.json';harness.write(target,report)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--study',required=True);p.add_argument('--proposals',required=True);p.add_argument('--history',required=True);p.add_argument('--directory',required=True);a=p.parse_args()
    print(json.dumps(register(a.study,json.loads(Path(a.proposals).read_text()),a.history,a.directory),indent=2,sort_keys=True))
