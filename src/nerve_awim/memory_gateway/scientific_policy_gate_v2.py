"""Policy-scoped reclassification; no inference or automatic promotion authority."""
from hashlib import sha256
import json
from pathlib import Path
import stat

from . import scientific_substrate_gate as predecessor
from . import scientific_substrate_calibration_v2 as calibration
from . import scientific_compact_dev_transport as compact
from .research_supervisor import _exclusive

VERSION='scientific-policy-gate-v2'
canonical=calibration.canonical
POLICY_NAMES=('candidate_v3','compact_with_abstain','original_json')


def sources():
    pins=predecessor.sources();pins.update(calibration.sources())
    for name in ('src/nerve_awim/memory_gateway/scientific_policy_gate_v2.py',
                 'src/nerve_awim/memory_gateway/scientific_candidate_v3.py',
                 'scripts/run_scientific_policy_gate_v2.py'):
        pins[name]=sha256((calibration.pilot.ROOT/name).read_bytes()).hexdigest()
    return pins


def _read(path):
    return json.loads(predecessor.study._read(path))


def adjudicate(calibration_directory,*,floor_directory=None):
    root=Path(calibration_directory).resolve()
    floor=Path(floor_directory).resolve() if floor_directory else root.parent/'scientific-substrate-gate-v1'
    pins=sources()
    published=_read(root/'report.json');p=published['protocol']
    checked=calibration.validate_receipt(root,p['expected_digest'],p['journal'],
        bank_directory=p['bank_directory'],bank_manifest_sha256=p['manifest_sha256'],
        predecessor_directory=p['predecessor_directory'],predecessor_journal=p['predecessor_journal'])
    if canonical(published)!=canonical(checked) or checked['status']!='complete':
        raise ValueError('completed_calibration_required')
    old=_read(floor/'report.json');study=_read(Path(old['study_directory'])/'report.json');q=study['protocol']
    prior=predecessor.adjudicate(old['study_directory'],q['expected_digest'],q['journal'],**q['paths'])
    if canonical(old)!=canonical(prior) or old['verdict']!='model_at_floor':
        raise ValueError('validated_prior_floor_required')
    if prior['model_digest']!=p['expected_digest'] or prior['model']!=p['model']:
        raise ValueError('same_substrate_reclassification_required')
    groups={a:[r for r in checked['rows'] if r['arm']==a] for a in ('compact','forced_answer','original')}
    if (any(len(g)!=10 for g in groups.values()) or
        any(r['response']['raw_output'].strip()!='ABSTAIN' for r in groups['compact']) or
        any(r['score']['declared_abstention'] for r in groups['forced_answer'])):
        raise ValueError('registered_reclassification_evidence_required')
    identity=calibration._hash({'system':compact.SYSTEM,'output_contract':'alias_triplet_or_abstain',
                               'scope':'prompt_policy_across_output_caps_and_model_digests'})
    result=dict(version=VERSION,verdict='prompt_induced_abstention',supersedes='model_at_floor',
        blocked_policy='compact_with_abstain',blocked_policy_sha256=identity,model_digest_blocked=False,
        proposals_unblocked=True,retired_policy='original_json',
        allowed_new_policies=['candidate_v3'],baseline_exception='comparison_only_no_promotion',
        calibration_directory=str(root),floor_directory=str(floor),
        calibration_receipt_sha256=calibration._hash(checked),prior_floor_receipt_sha256=calibration._hash(prior),
        evidence={'compact_abstentions':10,'forced_abstentions':0,'supported_items':10},
        interpretation='Policy-scoped operational reclassification; condition-major calibration does not prove a general model capability or isolate order effects.',
        source_sha256=pins,new_model_calls=0,holdout_accessed=False,promotion_authorized=False)
    if sources()!=pins:raise ValueError('policy_gate_sources_changed')
    return result


def authorize(policy_name,calibration_directory,*,purpose='proposal',floor_directory=None):
    if policy_name not in POLICY_NAMES or purpose not in ('proposal','development_baseline'):
        raise ValueError('registered_policy_and_purpose_required')
    decision=adjudicate(calibration_directory,floor_directory=floor_directory)
    allowed=policy_name=='candidate_v3' and purpose=='proposal' or policy_name=='compact_with_abstain' and purpose=='development_baseline'
    return dict(status='allowed' if allowed else 'blocked',policy=policy_name,purpose=purpose,
        reason='registered_new_policy' if policy_name=='candidate_v3' else 'comparison_only' if allowed else 'retired_original_prompt' if policy_name=='original_json' else 'prompt_induced_abstention',
        decision=decision,inference_authorized=False,promotion_authorized=False)


def register_proposal(calibration_directory,*,floor_directory=None):
    permission=authorize('candidate_v3',calibration_directory,floor_directory=floor_directory)
    body=dict(version='scientific-candidate-v3-registration',policy='candidate_v3',permission=permission,
        stages=['exact_current_evidence_abstention_gate','compact_forced_json_extraction'],
        gate_conditions=['conflict','unit_mismatch','missing_evidence','entity_mismatch'],
        prediction='Measurement-decoy and entity-decoy strata are the regression risk: the extractor may select a decoy value, unit or source despite schema-valid output.',
        metrics=['value','unit','provenance','strict'],seed=20261015,evaluated=False,promotion_authorized=False)
    return dict(body,proposal_sha256=calibration._hash(body))


def publish(directory,calibration_directory,*,proposal=False):
    root=Path(directory).resolve();cal=Path(calibration_directory).resolve()
    if root==cal or root in cal.parents or cal in root.parents:raise ValueError('separate_policy_report_required')
    value=register_proposal(cal) if proposal else adjudicate(cal)
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    if stat.S_IMODE(root.stat().st_mode)!=0o700:raise ValueError('private_policy_report_required')
    with _exclusive(root):calibration.smoke._save_exact(root/'report.json',value)
    return value
