"""Bounded cognitive cues, selected by existing hosts rather than a new agent runtime.

Approval methods are trusted-host primitives, not authorization endpoints. Hosts must
apply their existing tenant, reviewer and deployment controls before calling them.
No prompt, clinical policy, provider configuration or permission is altered here.
"""
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import re
from threading import RLock
import time

MODES = frozenset({'instruction', 'assistant_prefix'})
MAX_CUE_BYTES = 2048


def _text(value, name, limit=256):
    if type(value) is not str or not value.strip() or len(value.encode('utf-8')) > limit:
        raise ValueError('bounded nonempty ' + name + ' required')
    return value


def _tuple(value, name):
    if not isinstance(value, (tuple, list)) or not value:
        raise ValueError('nonempty ' + name + ' required')
    for item in value:
        _text(item, name)
    if len(set(value)) != len(value):
        raise ValueError('duplicate ' + name)
    return tuple(value)


@dataclass(frozen=True)
class ModelProfile:
    provider: str
    model: str
    revision: str
    tokenizer: str
    tokenizer_revision: str
    supported_modes: tuple = ()
    template_revision: str = 'unspecified'

    def __post_init__(self):
        for field in ('provider', 'model', 'revision', 'tokenizer', 'tokenizer_revision', 'template_revision'):
            _text(getattr(self, field), field)
        if not isinstance(self.supported_modes, (tuple, list)) or any(x not in MODES for x in self.supported_modes):
            raise ValueError('explicit supported cue modes required')
        object.__setattr__(self, 'supported_modes', tuple(sorted(set(self.supported_modes))))

    @property
    def key(self):
        # Capabilities are part of the binding: enabling a new mode requires retesting.
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


@dataclass(frozen=True)
class Cue:
    cue_id: str
    version: int
    text: str
    mode: str
    profile_key: str
    task_types: tuple
    provenance: str
    status: str = 'candidate'
    approval_id: str = None
    expires_at: float = None

    def __post_init__(self):
        for field in ('cue_id', 'profile_key', 'provenance'):
            _text(getattr(self, field), field, 2048 if field == 'provenance' else 256)
        if not re.fullmatch(r'[a-f0-9]{64}', self.profile_key):
            raise ValueError('exact model profile hash required')
        _text(self.text, 'cue text', MAX_CUE_BYTES)
        if type(self.version) is not int or self.version < 1 or self.mode not in MODES:
            raise ValueError('positive version and supported mode required')
        object.__setattr__(self, 'task_types', _tuple(self.task_types, 'task types'))
        if self.status not in ('candidate', 'approved', 'revoked'):
            raise ValueError('unknown cue status')
        if self.status == 'approved':
            _text(self.approval_id, 'approval ID')
        elif self.status == 'candidate' and self.approval_id is not None:
            raise ValueError('candidate cannot claim approval')
        if self.expires_at is not None:
            import math
            if type(self.expires_at) not in (int, float) or not math.isfinite(self.expires_at) or self.expires_at <= 0:
                raise ValueError('finite positive expiry required')

    @property
    def content_hash(self):
        fields = asdict(self)
        fields.pop('status'); fields.pop('approval_id')
        return hashlib.sha256(json.dumps(fields, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


# Defense in depth for short proposals. This is not a prompt-injection classifier;
# independent evaluation and host approval remain mandatory for every activation.
_FORBIDDEN = re.compile(r'ignore\s+(?:all\s+)?(?:previous|prior|system)|'
    r'bypass|disable\s+(?:safety|permission)|reveal\s+(?:secrets|system)|'
    r'<\|(?:im_start|im_end|system)|\[INST\]', re.I)


def safety_reason(cue):
    if _FORBIDDEN.search(cue.text):
        return 'unsafe_cue'
    if any(ord(c) < 32 and c not in '\n\t' for c in cue.text):
        return 'unsafe_cue'
    return None


class CueRegistry:
    """In-process immutable content versions; durable storage belongs to NERVE host."""
    def __init__(self):
        self._cues = {}
        self._lock = RLock()

    def register(self, cue):
        if not isinstance(cue, Cue) or cue.status != 'candidate' or cue.approval_id is not None:
            raise ValueError('only unapproved candidates may be registered')
        with self._lock:
            key = (cue.cue_id, cue.version)
            if key in self._cues:
                raise ValueError('cue versions are immutable')
            self._cues[key] = cue
        return cue

    def get(self, cue_id, version):
        with self._lock:
            return self._cues[(cue_id, version)]

    def candidates(self):
        with self._lock:
            return tuple(self._cues[key] for key in sorted(self._cues))

    def approve(self, cue_id, version, *, approval_id):
        _text(approval_id, 'host approval ID')
        with self._lock:
            cue = self.get(cue_id, version)
            if cue.status != 'candidate' or safety_reason(cue):
                raise PermissionError('only safe pending candidates can be approved')
            result = replace(cue, status='approved', approval_id=approval_id)
            self._cues[(cue_id, version)] = result
            return result

    def revoke(self, cue_id, version):
        with self._lock:
            cue = self.get(cue_id, version)
            result = replace(cue, status='revoked')
            self._cues[(cue_id, version)] = result
            return result


@dataclass(frozen=True)
class CueSelection:
    cue: Cue
    reason: str
    profile_key: str
    task_type: str

    def telemetry(self):
        """No task text, patient context or cue text enters selection telemetry."""
        return {'selected': self.cue is not None, 'reason': self.reason,
                'profile_key': self.profile_key, 'task_type': self.task_type,
                'cue_id': self.cue.cue_id if self.cue else None,
                'cue_version': self.cue.version if self.cue else None,
                'cue_hash': self.cue.content_hash if self.cue else None,
                'mode': self.cue.mode if self.cue else None,
                'approval_id': self.cue.approval_id if self.cue else None}


class CueRouter:
    def __init__(self, registry, *, enabled=False, clock=time.time):
        if not isinstance(registry, CueRegistry) or type(enabled) is not bool or not callable(clock):
            raise ValueError('registry, strict opt-in and clock required')
        self.registry, self.enabled, self.clock = registry, enabled, clock

    def select(self, profile, task_type, *, risk='low', clinical=False,
               permission_granted=False, cue_id=None, version=None):
        if not isinstance(profile, ModelProfile):
            raise ValueError('explicit model profile required')
        _text(task_type, 'task type')
        if type(clinical) is not bool or type(permission_granted) is not bool:
            raise ValueError('strict boolean policy decisions required')
        def selection(reason, cue=None):
            return CueSelection(cue, reason, profile.key, task_type)
        if not self.enabled:
            return selection('disabled')
        if not permission_granted:
            return selection('permission_denied')
        if clinical or task_type.lower() in ('clinical', 'medical', 'diagnosis', 'treatment'):
            return selection('clinical_disabled')
        if risk != 'low':
            return selection('risk_not_allowed')
        if not profile.supported_modes:
            return selection('unsupported_provider')
        if (cue_id is None) != (version is None):
            raise ValueError('cue ID and version must be specified together')
        matches = []
        for cue in self.registry.candidates():
            if cue_id is not None and (cue.cue_id, cue.version) != (cue_id, version):
                continue
            if (cue.status != 'approved' or cue.profile_key != profile.key
                    or cue.mode not in profile.supported_modes or task_type not in cue.task_types
                    or safety_reason(cue) or (cue.expires_at is not None and self.clock() >= cue.expires_at)):
                continue
            matches.append(cue)
        if not matches:
            return selection('no_eligible_cue')
        # Never silently choose between unrelated host-approved experiments.
        if len(matches) != 1:
            return selection('ambiguous_selection')
        return selection('selected', matches[0])


def inspect_tokenization(cue, profile, encode, *, max_tokens=128):
    """Offline inspection using a host-supplied exact tokenizer; never downloads.

    Measures cue text only. Provider-specific template composition needs a separate
    host test; this function does not claim instruction and prefix equivalence.
    Token IDs stay in the return value for reproducibility, never router telemetry.
    """
    if not isinstance(cue, Cue) or not isinstance(profile, ModelProfile) or not callable(encode):
        raise ValueError('cue, exact model profile and trusted tokenizer required')
    if cue.profile_key != profile.key or cue.mode not in profile.supported_modes:
        raise ValueError('profile or mode mismatch')
    if type(max_tokens) is not int or not 1 <= max_tokens <= 2048:
        raise ValueError('bounded positive token budget required')
    token_ids = encode(cue.text)
    if (not isinstance(token_ids, (list, tuple)) or not token_ids
            or len(token_ids) > max_tokens
            or any(type(x) is not int or x < 0 for x in token_ids)):
        raise ValueError('invalid encoding or cue token budget exceeded')
    return {'profile_key': profile.key, 'cue_hash': cue.content_hash,
            'token_count': len(token_ids), 'token_ids': tuple(token_ids),
            'mode': cue.mode, 'template_revision': profile.template_revision}
