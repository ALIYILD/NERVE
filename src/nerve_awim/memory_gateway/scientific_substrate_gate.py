"""Opt-in substrate gate over verified development evidence, never a weight update.

The metadata callback is trusted host identity verification, not caller attestation.
Calibration eligibility grants no inference authority and produces no proposals.
Legacy proposal APIs remain research primitives; callers must use gated_propose.
"""
from hashlib import sha256
from pathlib import Path
import re
import stat

from . import scientific_compact_dev_study as study
from . import scientific_candidates as candidates
from . import scientific_format_feedback as format_feedback
from .research_supervisor import _exclusive

VERSION='scientific-substrate-gate-v1'


def sources():
    result=study.sources();result.update(format_feedback.sources())
    for name in ('src/nerve_awim/memory_gateway/scientific_substrate_gate.py','scripts/run_scientific_substrate_gate.py'):
        result[name]=sha256((study.pilot.ROOT/name).read_bytes()).hexdigest()
    return result


def adjudicate(study_directory,expected_digest,journal,**study_inputs):
    pins=sources()
    report=study.validate_receipt(study_directory,expected_digest,journal,**study_inputs)
    if report['status']!='complete':raise ValueError('completed_development_evidence_required')
    rows=report['rows']
    model_rows=[r for r in rows if r['model_calls']==1]
    by_arm={arm:{r['task_id']:r['score']['strict_correct'] for r in rows if r['arm']==arm} for arm in study.ARMS}
    floor=(len(model_rows)==100 and all(r['raw_output'].strip()=='ABSTAIN' for r in model_rows)
           and by_arm['baseline']==by_arm['always_abstain']==by_arm['candidate'])
    if sources()!=pins:raise ValueError('gate_sources_changed')
    return dict(version=VERSION,status='model_at_floor' if floor else 'not_at_floor',
                verdict='model_at_floor' if floor else 'not_at_floor',
                policy_candidate_distinguishable=False if floor else None,conflict_rule_effect_tested=False if floor else None,
                abstaining_model_output_count=sum(r['raw_output'].strip()=='ABSTAIN' for r in model_rows),
                model_digest=expected_digest,model=report['protocol']['model'],
                study_directory=str(Path(study_directory).resolve()),
                receipt_sha256=study._hash(report),source_sha256=pins,
                model_output_count=len(model_rows),new_model_calls=0,holdout_opened=False,
                promotion_authorized=False,scope='This fixed development task distribution only.')


def _metadata(callback):
    if not callable(callback):raise TypeError('trusted_host_metadata_verifier_required')
    value=callback()
    if (type(value) is not dict or set(value)!={'model','digest'} or type(value['model']) is not str
            or not 1<=len(value['model'])<=200 or type(value['digest']) is not str
            or not re.fullmatch('[0-9a-f]{64}',value['digest'])):
        raise ValueError('verified_immutable_substrate_identity_required')
    return dict(value)


def _gated_propose(store,actor,*,family,study_directory,expected_digest,journal,substrate_metadata,
                  operation='proposal',research_agent_enabled=True,max_proposals=4,**study_inputs):
    if operation not in ('proposal','calibration'):raise ValueError('fixed_operation_required')
    if type(research_agent_enabled) is not bool or type(max_proposals) is not int or not 1<=max_proposals<=4:
        raise ValueError('bounded_proposal_configuration_required')
    # Even blocked requests require the original authoritative scoped permission.
    store.query(actor)
    decision=adjudicate(study_directory,expected_digest,journal,**study_inputs)
    identity=_metadata(substrate_metadata)
    same=identity['digest']==decision['model_digest']
    blocked=decision['status']=='model_at_floor' and same
    generation=None
    if operation=='calibration':
        status='calibration_only';reason='fixed_30_call_substrate_diagnostic_only'
    elif blocked:
        status='blocked';reason='model_at_floor_requires_verified_new_digest'
    else:
        generation=(candidates.propose(store,actor,research_agent_enabled=research_agent_enabled,max_proposals=max_proposals)
                    if family=='research' else format_feedback.propose(store,actor,identity['digest']))
        status='proposed';reason='verified_new_digest' if not same else 'not_at_floor'
    store.query(actor)
    if _metadata(substrate_metadata)!=identity or sources()!=decision['source_sha256']:
        raise ValueError('substrate_or_sources_changed')
    checked=adjudicate(study_directory,expected_digest,journal,**study_inputs)
    if study.canonical(checked)!=study.canonical(decision):raise ValueError('predecessor_receipt_changed')
    return dict(version=VERSION,status=status,reason=reason,proposal_family=family,adjudication=decision,substrate=identity,
                generation=generation,proposals=[] if generation is None else generation['proposals'],
                calibration=(dict(kind='scientific-substrate-calibration-30-v1',max_model_calls=30,proposal_generation=False)
                             if operation=='calibration' else None),
                new_model_calls=0,holdout_opened=False,promotion_authorized=False,
                inference_authorized=False)


def gated_propose(store,actor,**kwargs):
    return _gated_propose(store,actor,family='research',**kwargs)


def gated_format_propose(store,actor,**kwargs):
    return _gated_propose(store,actor,family='format',**kwargs)


def publish_adjudication(directory,study_directory,expected_digest,journal,**study_inputs):
    root=Path(directory).resolve()
    protected=[Path(study_directory).resolve(),Path(journal).resolve()]
    protected.extend(Path(value).resolve() for key,value in study_inputs.items() if key.endswith('_directory'))
    if any(root==p or root in p.parents or p in root.parents for p in protected):
        raise ValueError('separate_adjudication_directory_required')
    result=adjudicate(study_directory,expected_digest,journal,**study_inputs)
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    if stat.S_IMODE(root.stat().st_mode)!=0o700:raise ValueError('private_adjudication_directory_required')
    with _exclusive(root):
        if sources()!=result['source_sha256']:raise ValueError('gate_sources_changed')
        study.smoke._save_exact(root/'report.json',result)
    return result
