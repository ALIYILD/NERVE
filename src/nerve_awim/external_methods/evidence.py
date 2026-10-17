"""Content-addressed replay, rejection archive and skill records (Voyager/Reflexion/DGM)."""
import json
import os
from pathlib import Path
import sqlite3

from .contracts import canonical, digest, validate_patch, route


class ResponseCache:
    def __init__(self, directory, *, split='dev'):
        if split not in ('dev', 'holdout', 'synthetic'): raise ValueError('known_split_required')
        self.root, self.split = Path(directory), split
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.root.is_symlink() or self.root.stat().st_mode & 0o077:
            raise ValueError('private_cache_directory_required')

    def put(self, request, response):
        if set(request) != {'model_digest', 'prompt', 'params', 'replicate'}:
            raise ValueError('full_request_identity_required')
        # Replicate distinguishes repeated stochastic draws with otherwise equal inputs.
        key = digest(request)
        value = {'request': request, 'response': response, 'response_sha256': digest(response)}
        path = self.root / (key + '.json')
        encoded = canonical(value).encode()
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            if self.get(key) != value: raise ValueError('cache_response_changed')
        else:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(encoded); stream.flush(); os.fsync(stream.fileno())
        return key

    def get(self, key):
        if len(key) != 64 or any(c not in '0123456789abcdef' for c in key): raise ValueError('cache_key_required')
        path = self.root / (key + '.json')
        if path.is_symlink(): raise ValueError('cache_symlink')
        value = json.loads(path.read_text())
        if digest(value['request']) != key or digest(value['response']) != value['response_sha256']:
            raise ValueError('cache_integrity_failure')
        return value

    def manifest(self, *, public=True):
        entries = []
        for path in sorted(self.root.glob('*.json')):
            value = self.get(path.stem)
            entries.append({'request_sha256': path.stem, 'response_sha256': value['response_sha256']})
        if self.split == 'holdout' and public:
            return {'split': self.split, 'entries': len(entries), 'private_manifest_sha256': digest(entries)}
        return {'split': self.split, 'entries': entries}


class Archive:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS records (hash TEXT PRIMARY KEY, body TEXT NOT NULL)')

    def retain(self, candidate, *, bank, model, incumbent, study, verdict, lesson=None):
        if verdict not in ('rejected', 'retained', 'insufficient_power', 'incomplete_infrastructure'):
            raise ValueError('archive_verdict_required')
        if lesson is not None and (type(lesson) is not str or len(lesson) > 4096): raise ValueError('bounded_lesson_required')
        body = dict(candidate=candidate, bank=bank, model=model, incumbent=incumbent,
                    study=study, verdict=verdict, lesson=lesson, lesson_role='generator_input_only')
        identity = digest(body)
        with self.db: self.db.execute('INSERT OR IGNORE INTO records VALUES (?,?)', (identity, canonical(body)))
        return identity

    def eligible(self, identity, *, bank, model, incumbent):
        row = self.db.execute('SELECT body FROM records WHERE hash=?', (identity,)).fetchone()
        if row is None or digest(json.loads(row[0])) != identity: raise ValueError('archive_integrity_failure')
        old = json.loads(row[0])
        changed = [k for k, v in dict(bank=bank, model=model, incumbent=incumbent).items() if old[k] != v]
        return {'eligible': bool(changed), 'changed': changed, 'prior_record': identity}


def skill_record(*, skill_id, version, patch, description, evidence_bundle, capacity_delta,
                 supersedes=None, signed_by=None, usage=None):
    validate_patch(patch)
    if not signed_by or not evidence_bundle or not description: raise ValueError('reviewed_skill_evidence_required')
    return dict(skill_id=skill_id, version=version, seam=patch['seam'], patch=patch['patch'],
                description=description, evidence_bundle=evidence_bundle, capacity_delta=capacity_delta,
                usage=usage or {'selected': 0, 'outcomes': []}, supersedes=supersedes, signed_by=signed_by)


class SkillLibrary:
    """Retrieve retained skills by seam and diagnosed regime, recording usage."""
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS skills (identity TEXT PRIMARY KEY, seam TEXT, regime TEXT, body TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS skill_usage (identity TEXT, episode TEXT, outcome TEXT, PRIMARY KEY(identity,episode))')

    def add(self, record, regime):
        from .contracts import ROUTES
        if record['seam'] not in ROUTES.get(regime, []) or not record.get('signed_by'):
            raise ValueError('reviewed_seam_regime_skill_required')
        identity = digest(record)
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO skills VALUES (?,?,?,?)', (identity, record['seam'], regime, canonical(record)))
        return identity

    def retrieve(self, seam, regime):
        rows = self.db.execute('SELECT identity,body FROM skills WHERE seam=? AND regime=? ORDER BY identity', (seam, regime))
        result = []
        for identity, body in rows:
            value = json.loads(body)
            if digest(value) != identity: raise ValueError('skill_integrity_failure')
            result.append(value)
        return result

    def record_usage(self, identity, episode, outcome):
        if not self.db.execute('SELECT 1 FROM skills WHERE identity=?', (identity,)).fetchone():
            raise ValueError('retained_skill_required')
        encoded = canonical(outcome)
        with self.db:
            old = self.db.execute('SELECT outcome FROM skill_usage WHERE identity=? AND episode=?', (identity, episode)).fetchone()
            if old and old[0] != encoded: raise ValueError('skill_outcome_changed')
            self.db.execute('INSERT OR IGNORE INTO skill_usage VALUES (?,?,?)', (identity, episode, encoded))
        rows = self.db.execute('SELECT episode,outcome FROM skill_usage WHERE identity=? ORDER BY episode', (identity,)).fetchall()
        return {'selected': len(rows), 'outcomes': [{'episode': e, 'outcome': json.loads(o)} for e,o in rows]}


class RepairPlanner:
    """Durable proposal budgets and rotation. No model calls or code execution."""
    def __init__(self, path, *, budget=3):
        if type(budget) is not int or budget < 1: raise ValueError('positive_budget_required')
        self.budget = budget
        self.db = sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS repairs (study TEXT PRIMARY KEY, histogram TEXT, body TEXT)')

    def propose(self, study_id, histogram):
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            old = self.db.execute('SELECT histogram,body FROM repairs WHERE study=?', (study_id,)).fetchone()
            if old:
                if old[0] != canonical(histogram): raise ValueError('repair_evidence_changed')
                return json.loads(old[1])
            attempts = {}
            for (raw,) in self.db.execute('SELECT body FROM repairs'):
                prior = json.loads(raw)
                if prior['status'] == 'proposed':
                    key = prior['regime'] + ':' + prior['seam']; attempts[key] = attempts.get(key, 0) + 1
            proposal = route(histogram, attempts, self.budget)
            if proposal['status'] == 'proposed':
                patches = {'abstention-rule': {'rule': 'recency' if proposal['regime'] == 'stale_selected' else 'evidence_required'},
                    'extraction-schema': {'fields': ['value', 'unit', 'source_id']},
                    'prompt-fragment': {'text': 'Check that the cited source matches the requested entity, measurement, unit and value.'},
                    'retrieval-order': {'order': 'current_first' if proposal['regime'] == 'stale_selected' else 'exact_match_first'}}
                if proposal['regime'] == 'conflict_not_detected': patches['abstention-rule'] = {'rule': 'conflict'}
                patch = {'seam': proposal['seam'], 'patch': patches[proposal['seam']]}
                proposal.update(patch=patch, patch_sha256=validate_patch(patch), model_calls=0, promotion_authorized=False)
            self.db.execute('INSERT INTO repairs VALUES (?,?,?)', (study_id, canonical(histogram), canonical(proposal)))
        return proposal


def evidence_requirements(tier):
    requirements = ['sequential_gate', 'regression_suite', 'rollback', 'human_signature']
    if tier not in ('A', 'B', 'C'): raise ValueError('evidence_tier_required')
    if tier in ('B', 'C'): requirements += ['cost_constraints', 'latency_constraints', 'permission_constraints']
    if tier == 'C': requirements += ['isolated_evaluation', 'safety_suite', 'shadow_canary', 'named_owner']
    return requirements


def review_readiness(tier, evidence):
    missing = [k for k in evidence_requirements(tier) if not evidence.get(k)]
    return {'ready_for_review': not missing, 'missing': missing, 'promotion_authorized': False}


def probe_status(*, model_parameters=0, gpu=False, toolkit_reviewed=False, validation=None):
    if model_parameters < 7_000_000_000 or not gpu or not toolkit_reviewed:
        return {'status': 'white-box: unavailable', 'output_verifier_enabled': True, 'promotion_authorized': False}
    if not validation:
        return {'status': 'requires_preregistered_probe_study', 'output_verifier_enabled': True, 'promotion_authorized': False}
    # No unvalidated probes enter the gate, including attractive post-hoc correlations.
    required = ('preregistered', 'held_out_dev', 'steering_confirmed', 'tier_c_signed')
    accepted = all(validation.get(k) is True for k in required)
    from .contracts import number
    accepted &= number(validation.get('predictive_power', 0), 0, 1) >= number(validation.get('threshold', 1), 0, 1)
    return {'status': 'research_probe_validated' if accepted else 'retired',
            'output_verifier_enabled': True, 'promotion_authorized': False,
            'live_verifier_enabled': False}
