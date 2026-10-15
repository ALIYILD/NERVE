"""Bounded candidate collection around NERVE's existing Hermes discovery role.

Imported paper text is host-supplied evidence, not verified by this module. Its
source, revision, locator, model and injection mode remain attached to the cue.
Collection never evaluates, registers, approves or activates a candidate. Provider
billing, retries and timeouts remain enforced by the existing host adapter.
"""
from dataclasses import asdict, dataclass
import hashlib
import json

from .cue_engine import Cue, ModelProfile, MODES, MAX_CUE_BYTES, safety_reason
from .cue_evaluation import DatasetManifest, discover_candidates


def _bounded_text(value, name, limit=512):
    if type(value) is not str or not value.strip() or len(value.encode()) > limit:
        raise ValueError('bounded nonempty ' + name + ' required')


def _text_digest(text):
    return hashlib.sha256(text.encode()).hexdigest() if type(text) is str else None


@dataclass(frozen=True)
class PaperCandidate:
    text: str
    source_url: str
    source_revision: str
    source_locator: str
    source_model: str
    mode: str = 'assistant_prefix'

    def __post_init__(self):
        _bounded_text(self.text, 'paper cue', MAX_CUE_BYTES)
        for name in ('source_url', 'source_revision', 'source_locator', 'source_model'):
            _bounded_text(getattr(self, name), name, 256)
        if not self.source_url.startswith('https://') or self.mode not in MODES:
            raise ValueError('HTTPS source and explicit supported paper mode required')


@dataclass(frozen=True)
class DiscoveryRejection:
    stage: str
    reason: str
    content_digest: str = None
    source_index: int = None
    call_index: int = None


@dataclass(frozen=True)
class DiscoveryBatch:
    candidates: tuple
    rejections: tuple
    attempted_calls: int

    def telemetry(self):
        """No raw cue, discovery IDs, source text or exception messages in audit."""
        return {'candidate_hashes': [cue.content_hash for cue in self.candidates],
                'candidate_count': len(self.candidates), 'attempted_calls': self.attempted_calls,
                'rejections': [asdict(receipt) for receipt in self.rejections],
                'approved': False}


def discover_cue_pool(execute, manifest, profile, task_type, *, tenant, agent,
                      generator_id, paper_candidates=(), max_candidates=16,
                      max_calls=2, per_call_candidates=4, permission_granted=False,
                      clinical=False, risk='low', learning_context=None):
    """Return at most 64 unapproved proposals with explicit rejection receipts.

    Duplicate identity is exact UTF-8 text plus injection mode for this profile.
    Whitespace is preserved: token-level prefix experiments cannot normalize it.
    One invalid callback response rejects that response, not earlier valid cues;
    exhausted budgets stop collection. Exceptions never trigger hidden retries.
    A paper prefix is never silently converted into an instruction.
    """
    if permission_granted is not True or clinical is not False or risk != 'low':
        raise PermissionError('explicit permission and low-risk nonclinical discovery required')
    for value, name in ((task_type, 'task type'), (tenant, 'tenant'), (agent, 'agent'),
                        (generator_id, 'generator ID')):
        _bounded_text(value, name, 256)
    if task_type.lower() in ('clinical', 'medical', 'diagnosis', 'treatment'):
        raise PermissionError('clinical cue discovery disabled')
    if not isinstance(manifest, DatasetManifest) or not isinstance(profile, ModelProfile):
        raise TypeError('frozen manifest and exact model profile required')
    if learning_context is not None:
        from .cue_feedback import validate_learning_context
        learning_context = validate_learning_context(learning_context,
            profile_key=profile.key, task_type=task_type)
    for value, lower, upper in ((max_candidates, 1, 64), (max_calls, 0, 8), (per_call_candidates, 1, 16)):
        if type(value) is not int or not lower <= value <= upper:
            raise ValueError('bounded integer discovery budgets required')
    if not isinstance(paper_candidates, (tuple, list)) or len(paper_candidates) > 64:
        raise ValueError('at most 64 frozen paper candidates required')
    if max_calls and not callable(execute):
        raise ValueError('existing Hermes execute adapter required')
    candidates, rejections, seen = [], [], set()
    attempted = 0

    def reject(stage, reason, text=None, source_index=None, call_index=None):
        rejections.append(DiscoveryRejection(stage, reason, _text_digest(text), source_index, call_index))

    def accept(text, mode, provenance, stage, source_index=None, call_index=None):
        if mode not in profile.supported_modes:
            reject(stage, 'unsupported_mode', text, source_index, call_index)
            return
        identity = (mode, text)
        if identity in seen:
            reject(stage, 'duplicate_content', text, source_index, call_index)
            return
        # Mark rejected unsafe/budgeted content too, preventing repeated retries.
        seen.add(identity)
        cue_id = hashlib.sha256((profile.key + '\0' + mode + '\0' + text).encode()).hexdigest()
        try:
            cue = Cue(cue_id, 1, text, mode, profile.key, (task_type,), provenance)
        except ValueError:
            reject(stage, 'invalid_candidate', text, source_index, call_index)
            return
        if safety_reason(cue):
            reject(stage, 'unsafe_candidate', text, source_index, call_index)
            return
        if len(candidates) >= max_candidates:
            reject(stage, 'candidate_cap', text, source_index, call_index)
            return
        candidates.append(cue)

    for index, imported in enumerate(paper_candidates):
        if not isinstance(imported, PaperCandidate):
            reject('paper', 'invalid_import', source_index=index)
            continue
        provenance = {key: value for key, value in asdict(imported).items() if key != 'text'}
        provenance['kind'] = 'paper_import_unverified'
        accept(imported.text, imported.mode, json.dumps(provenance, sort_keys=True), 'paper', index)

    while attempted < max_calls and len(candidates) < max_candidates:
        if 'instruction' not in profile.supported_modes:
            reject('hermes', 'unsupported_mode')
            break
        limit = min(per_call_candidates, max_candidates - len(candidates))
        attempted += 1

        def adapter(role, payload, **scope):
            result = execute(role, payload, **scope)
            # Existing contract rejects duplicates; retain its bounded schema while
            # making exact duplicates explicit per-item rejection receipts.
            if (type(result) is dict and set(result) == {'candidates'}
                    and type(result['candidates']) is list and len(result['candidates']) <= limit
                    and all(type(text) is str and text.strip() and len(text) <= 512
                            for text in result['candidates'])):
                unique, local_seen = [], set()
                for index, text in enumerate(result['candidates']):
                    if text in local_seen:
                        reject('hermes', 'duplicate_content', text, index, attempted)
                    else:
                        local_seen.add(text)
                        unique.append(text)
                return {'candidates': unique}
            return result

        try:
            proposals = discover_candidates(adapter, manifest, tenant=tenant, agent=agent,
                max_candidates=limit, learning_context=learning_context)
        except PermissionError:
            # A denied host capability cannot be bypassed with another dispatch.
            reject('hermes', 'permission_denied', call_index=attempted)
            break
        except Exception:
            reject('hermes', 'invalid_response_or_adapter_failure', call_index=attempted)
            break
        if not proposals:
            reject('hermes', 'empty_response', call_index=attempted)
            break
        for index, text in enumerate(proposals):
            provenance = json.dumps({'kind': 'hermes_discovery', 'generator_id': generator_id,
                                     'call_index': attempted}, sort_keys=True)
            accept(text, 'instruction', provenance, 'hermes', index, attempted)
    if attempted == max_calls and max_calls and len(candidates) < max_candidates:
        reject('budget', 'call_cap')
    return DiscoveryBatch(tuple(candidates), tuple(rejections), attempted)
