"""Trusted AgentOS CCE adapter; no scheduler, provider execution or auto-approval.

Configuration names an exact model profile, but cannot attest the real worker.
Native workers must independently match its installed runtime before applying
an envelope. Public receipts never include cue text, tasks or credentials.
"""
from dataclasses import asdict, fields
import json
import sqlite3

from .agentos_learning import AgentOSLearning, atomic_json
from .agent_learning_v12 import RegisteredStrategy
from .cue_engine import ModelProfile
from .cue_learning import GovernedCueCoordinator
from .governed_learning_v20 import GovernedLearning, LearningAuthority, _id

CONTRACT = 'cce-host-v1'
TENANT = 'agentos-local'
_UNPINNED = frozenset(('unknown', 'unspecified', 'latest', 'default', 'auto', 'none'))


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('duplicate config key')
        value[key] = item
    return value


class CueHost:
    def __init__(self, host, *, uncertainty=None):
        if not isinstance(host, AgentOSLearning):
            raise TypeError('existing AgentOS learning host required')
        self.host = host
        self.uncertainty = uncertainty
        self._authority = LearningAuthority()
        self._engine = None

    def _config(self):
        path = self.host.directory / 'cce-config.json'
        if not path.exists():
            return {}, 'not_configured'
        try:
            if path.stat().st_size > 65536:
                raise ValueError('oversized configuration')
            data = json.loads(path.read_text(), object_pairs_hook=_object,
                              parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite config')))
            if type(data) is not dict or set(data) != {'enabled', 'profiles'} or type(data['enabled']) is not bool:
                raise ValueError('strict config schema required')
            entries = data['profiles']
            if type(entries) is not dict or len(entries) > 32:
                raise ValueError('bounded profiles required')
            profiles = {}
            for name, entry in entries.items():
                _id(name)
                if type(entry) is not dict or set(entry) != {'model_profile', 'task_type'} or entry['task_type'] != 'handoff':
                    raise ValueError('handoff-only profile config required')
                raw = entry['model_profile']
                if type(raw) is not dict or set(raw) != {f.name for f in fields(ModelProfile)}:
                    raise ValueError('complete model profile required')
                profile = ModelProfile(**raw)
                if profile.supported_modes != ('instruction',):
                    raise ValueError('instruction-only host profile required')
                if any(getattr(profile, field).strip().lower() in _UNPINNED for field in
                       ('provider', 'model', 'revision', 'tokenizer', 'tokenizer_revision', 'template_revision')):
                    raise ValueError('exact pinned profile required')
                profiles[name] = profile
            return profiles, 'enabled' if data['enabled'] else 'disabled'
        except (OSError, ValueError, TypeError):
            return {}, 'invalid_config'

    def _actor(self, profile, role):
        return self._authority.issue(TENANT, _id(profile), role)

    def _coordinator(self, profile):
        _id(profile)
        if self._engine is None:
            self._engine = GovernedLearning(self.host.path, authority=self._authority,
                strategies=[RegisteredStrategy('no-cue', 'handoff', lambda value: None)],
                judge=lambda task, value: False, contract_revision=CONTRACT,
                baseline_routes={'handoff': 'no-cue'})
        with self._engine._db() as con:
            existing = con.execute('SELECT contract FROM gl_state WHERE tenant=? AND agent=?',
                                   (TENANT, profile)).fetchone()
        if existing is None:
            self._engine.bootstrap(self._actor(profile, 'operator'))
        elif existing['contract'] != CONTRACT:
            raise ValueError('existing learning scope has a different contract')
        return GovernedCueCoordinator(self._engine, enabled=True, uncertainty=self.uncertainty)

    def status(self, profile=None):
        profiles, state = self._config()
        if profile is not None:
            _id(profile)
        names = sorted(profiles) if profile is None else [profile]
        result = {'enabled': state == 'enabled', 'reason': state, 'profiles': {}}
        # Status does not create an engine, bootstrap a scope or select a cue.
        with sqlite3.connect(self.host.path) as con:
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for name in names:
                configured = profiles.get(name)
                details = {'configured': configured is not None,
                           'profile_key': configured.key if configured else None,
                           'task_type': 'handoff' if configured else None, 'active_candidate': None}
                if configured and 'cce_routes' in tables:
                    row = con.execute('SELECT active FROM cce_routes WHERE tenant=? AND agent=? AND contract=? AND task_type=? AND profile=?',
                        (TENANT, name, CONTRACT, 'handoff', configured.key)).fetchone()
                    details['active_candidate'] = row[0] if row else None
                result['profiles'][name] = details
        return result

    def inspect(self, profile, candidate):
        _id(profile); _id(candidate)
        return self._coordinator(profile).status(self._actor(profile, 'auditor'), candidate)

    def revoke(self, profile, candidate, *, reason):
        _id(profile); _id(candidate)
        coordinator = self._coordinator(profile)
        coordinator.revoke(self._actor(profile, 'operator'), candidate, reason=reason)
        return coordinator.status(self._actor(profile, 'auditor'), candidate)

    def _result(self, profile, reason, *, envelope=None, candidate=None, profile_key=None):
        receipt = {'profile': profile, 'reason': reason, 'candidate': candidate,
                   'profile_key': profile_key, 'envelope_prepared': envelope is not None,
                   'worker_attestation_required': envelope is not None}
        atomic_json(self.host.directory / 'cce-last-receipt.json', receipt)
        return {'envelope': envelope, 'receipt': receipt}

    def _uncertainty_required(self, profile, task_type):
        if self.uncertainty is not None:
            return True
        with sqlite3.connect(self.host.path) as con:
            exists = con.execute("SELECT 1 FROM sqlite_master WHERE name='cce_uncertainty_bindings'").fetchone()
            return bool(exists and con.execute('SELECT 1 FROM cce_uncertainty_bindings WHERE tenant=? AND agent=? AND contract=? AND context=?',
                (TENANT, profile, CONTRACT, task_type)).fetchone())

    def prepare(self, profile, task_type, *, permission_granted=False, clinical=False, risk='low'):
        _id(profile)
        uncertainty_state = None
        if self._uncertainty_required(profile, task_type):
            # This is an action restriction, not a cue preference. Never let the
            # optional no-cue fallback erase an opted-in uncertainty denial.
            uncertainty_state = self._coordinator(profile).uncertainty_state(
                self._actor(profile, 'runtime'), task_type, require_learning=True)
        profiles, state = self._config()
        if state != 'enabled':
            return self._result(profile, state)
        model = profiles.get(profile)
        if model is None:
            return self._result(profile, 'unconfigured_profile')
        if task_type != 'handoff' or clinical is not False or risk != 'low' or permission_granted is not True:
            return self._result(profile, 'context_denied', profile_key=model.key)
        try:
            coordinator = self._coordinator(profile)
            selected = coordinator.select(self._actor(profile, 'runtime'), model, task_type,
                risk=risk, clinical=clinical, permission_granted=permission_granted)
            if selected.cue is None:
                return self._result(profile, selected.reason, profile_key=model.key)
            cue = selected.cue
            if cue.mode != 'instruction':
                return self._result(profile, 'unsupported_mode', profile_key=model.key)
            candidate = cue.approval_id
            approved = coordinator.status(self._actor(profile, 'auditor'), candidate)
            envelope = {'profile': asdict(model), 'cue': asdict(cue), 'task_type': task_type,
                        'approval_expires': approved['expires']}
            result = self._result(profile, 'awaiting_worker_attestation', envelope=envelope,
                                  candidate=candidate, profile_key=model.key)
            if uncertainty_state is not None:
                result['uncertainty'] = coordinator.uncertainty_state(
                    self._actor(profile, 'runtime'), task_type, require_learning=True)
            return result
        except (ValueError, LookupError, PermissionError, sqlite3.Error):
            if self._uncertainty_required(profile, task_type):
                raise
            return self._result(profile, 'host_state_unavailable', profile_key=model.key)

    def feedback(self, profile, candidate, *, episode_id, safe, correct):
        """Trusted local outcomes only; agents may not assign their own rewards."""
        coordinator = self._coordinator(profile)
        coordinator.feedback(self._actor(profile, 'evaluator'), candidate,
                             episode_id=episode_id, safe=safe, correct=correct)
        return coordinator.status(self._actor(profile, 'auditor'), candidate)

    def export_memory(self, profile, candidate):
        coordinator = self._coordinator(profile)
        return coordinator.export_memory(self._actor(profile, 'auditor'), candidate,
                                         self.host.ledger, self.host.actor(profile))
