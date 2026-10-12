"""CCE extension of NERVE's existing authority, SQLite ledger and audit stream.

This is a trusted local host API, not an authentication service. It cannot grant
tool permissions or clinical approval. Outcomes/receipts must come from trusted
host evaluators; SQL and host Python code are within the existing trust boundary.
"""
from dataclasses import asdict
import json
import math
from hashlib import sha256
from pathlib import Path
import time
import uuid

from .cue_engine import Cue, CueRegistry, CueRouter, CueSelection, ModelProfile, safety_reason
from .cue_evaluation import evaluate_pairs, promotion_decision, IndependentReceipt, ModelParity
from .governed_learning_v20 import GovernedLearning, _id, _json


class GovernedCueCoordinator:
    def __init__(self, engine, *, enabled=False, clock=time.time, uncertainty=None):
        if not isinstance(engine, GovernedLearning) or type(enabled) is not bool or not callable(clock):
            raise TypeError('existing governed engine, explicit opt-in and clock required')
        self.engine, self.enabled, self.clock = engine, enabled, clock
        self.uncertainty = uncertainty
        with engine._db() as con:
            con.executescript('''
              CREATE TABLE IF NOT EXISTS cce_uncertainty_bindings (
                tenant TEXT,agent TEXT,contract TEXT,context TEXT,task TEXT,dependencies TEXT,required INTEGER,
                PRIMARY KEY(tenant,agent,contract,context));
              CREATE TABLE IF NOT EXISTS cce_candidates (
                id TEXT PRIMARY KEY, tenant TEXT, agent TEXT, contract TEXT,
                cue TEXT, profile TEXT, task_type TEXT, generator TEXT,
                manifest TEXT, report TEXT, status TEXT, expires REAL,
                UNIQUE(tenant,agent,contract,cue));
              CREATE TABLE IF NOT EXISTS cce_partitions (
                tenant TEXT, agent TEXT, contract TEXT, task TEXT, split TEXT,
                candidate TEXT, PRIMARY KEY(tenant,agent,contract,task));
              CREATE TABLE IF NOT EXISTS cce_routes (
                tenant TEXT, agent TEXT, contract TEXT, task_type TEXT,
                profile TEXT, active TEXT, generation INTEGER,
                PRIMARY KEY(tenant,agent,contract,task_type,profile));
              CREATE TABLE IF NOT EXISTS cce_feedback (
                candidate TEXT, episode TEXT, safe INTEGER, correct INTEGER,
                PRIMARY KEY(candidate,episode));
              CREATE TABLE IF NOT EXISTS cce_studies (
                id TEXT PRIMARY KEY, tenant TEXT, agent TEXT, contract TEXT,
                manifest TEXT, status TEXT);
              CREATE TABLE IF NOT EXISTS cce_versions (
                tenant TEXT, agent TEXT, contract TEXT, cue_id TEXT, version INTEGER,
                digest TEXT, candidate TEXT,
                PRIMARY KEY(tenant,agent,contract,cue_id,version));
            ''')

    def uncertainty_state(self, actor, task_type, *, require_learning=False):
        """Host opt-in persists; a replacement coordinator cannot omit the gate."""
        scope = self._scope(actor, 'runtime', 'operator', 'trainer', 'evaluator', 'auditor')
        _id(task_type)
        with self.engine._db() as con:
            binding = con.execute('SELECT * FROM cce_uncertainty_bindings WHERE tenant=? AND agent=? AND contract=? AND context=?',
                (*scope, self.engine.contract, task_type)).fetchone()
        adapter = self.uncertainty
        if adapter is None:
            if binding:
                raise PermissionError('uncertainty-enabled CCE context requires its scoped adapter')
            return None
        from .uncertainty.adapters import UncertaintyAdapter
        if not isinstance(adapter, UncertaintyAdapter):
            raise TypeError('host UncertaintyAdapter required')
        adapter.ledger.engine._scope(adapter.actor, 'runtime', 'operator')
        if ((adapter.actor.tenant, adapter.actor.agent) != scope or
                Path(adapter.ledger.engine.path).resolve() != Path(self.engine.path).resolve()):
            raise PermissionError('CCE and uncertainty require the same store and authenticated scope')
        # Validate every declared dependency before persisting the opt-in.
        known = {c.claim_id for c in adapter.ledger.claims(adapter.actor, adapter.task_id)}
        if not set(adapter.dependencies) <= known:
            raise PermissionError('CCE dependency source is unavailable')
        expected = (adapter.task_id, _json(sorted(adapter.dependencies)), int(adapter.required))
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            binding = con.execute('SELECT * FROM cce_uncertainty_bindings WHERE tenant=? AND agent=? AND contract=? AND context=?',
                (*scope, self.engine.contract, task_type)).fetchone()
            if binding and (binding['task'], binding['dependencies'], binding['required']) != expected:
                raise PermissionError('CCE uncertainty dependencies are immutable; new reviewed context required')
            con.execute('INSERT OR IGNORE INTO cce_uncertainty_bindings VALUES(?,?,?,?,?,?,?)',
                        (*scope, self.engine.contract, task_type, *expected))
        if require_learning:
            decision = 'cce-' + sha256((adapter.task_id + ':' + task_type).encode()).hexdigest()
            assessment = adapter.policy.assess(adapter.actor, adapter.task_id, decision,
                'cue-guidance', adapter.dependencies, impact='restricted', required=adapter.required)
            if assessment.status not in ('proceed', 'proceed_with_qualification'):
                raise PermissionError('required cue evidence remains unresolved')
        envelope = adapter.propagator.envelope(adapter.actor, adapter.task_id)
        if envelope['state'] != 'complete':
            raise PermissionError('complete authoritative CCE uncertainty state required')
        return envelope

    def _uncertainty_recheck(self, con, actor, task_type, envelope):
        binding = con.execute('SELECT task FROM cce_uncertainty_bindings WHERE tenant=? AND agent=? AND contract=? AND context=?',
            (*self._scope(actor, 'runtime', 'operator', 'trainer', 'evaluator', 'auditor'), self.engine.contract, task_type)).fetchone()
        if binding and (self.uncertainty is None or envelope is None):
            raise PermissionError('persisted CCE uncertainty gate cannot be omitted')
        if envelope is not None and self.uncertainty.ledger.revision(self.uncertainty.actor, binding['task'], con=con) != envelope['ledger_revision']:
            raise ValueError('uncertainty changed before CCE boundary; reassess')

    def _scope(self, actor, *roles):
        return self.engine._scope(actor, *roles)

    def _row(self, con, scope, candidate):
        self.engine._state(con, scope)
        row = con.execute('SELECT * FROM cce_candidates WHERE id=? AND tenant=? AND agent=? AND contract=?',
                          (candidate, *scope, self.engine.contract)).fetchone()
        if row is None:
            raise LookupError('cue candidate not available in current scope/contract')
        return row

    def _reserve(self, con, scope, manifest):
        reservation = uuid.uuid4().hex
        for split in ('discovery', 'selection', 'holdout'):
            for task in getattr(manifest, split):
                previous = con.execute('SELECT split FROM cce_partitions WHERE tenant=? AND agent=? AND contract=? AND task=?',
                    (*scope, self.engine.contract, task)).fetchone()
                if previous and (previous['split'] != split or split == 'holdout'):
                    raise ValueError('reserved/previously used holdout or changed dataset split')
                con.execute('INSERT OR IGNORE INTO cce_partitions VALUES(?,?,?,?,?,?)',
                    (*scope, self.engine.contract, task, split, reservation))
        con.execute('INSERT INTO cce_studies VALUES(?,?,?,?,?,?)',
            (reservation, *scope, self.engine.contract, _json(asdict(manifest)), 'reserved'))
        return reservation

    def reserve_study(self, actor, manifest):
        """Claim untouched holdout before any discovery spending; never release it."""
        from .cue_evaluation import DatasetManifest
        scope = self._scope(actor, 'trainer')
        if not isinstance(manifest, DatasetManifest):
            raise TypeError('disjoint dataset manifest required')
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            self.engine._state(con, scope)
            reservation = self._reserve(con, scope, manifest)
            self.engine._event(con, scope, 'cce_study_reserved', {'reservation': reservation})
        return reservation

    def propose(self, actor, cue, profile, task_type, manifest, *, generator_id, model_config, reservation=None):
        scope = self._scope(actor, 'trainer')
        _id(task_type); _id(generator_id)
        registry = CueRegistry()
        registry.register(cue)
        if (not isinstance(profile, ModelProfile) or cue.profile_key != profile.key
                or cue.task_types != (task_type,) or cue.mode not in profile.supported_modes
                or safety_reason(cue)):
            raise ValueError('safe candidate for one exact model and task context required')
        from .cue_evaluation import DatasetManifest
        if not isinstance(manifest, DatasetManifest):
            raise TypeError('preregistered disjoint dataset manifest required')
        if not isinstance(model_config, ModelParity) or model_config.profile_key != profile.key:
            raise ValueError('preregistered exact inference configuration required')
        for field in ('provider', 'model', 'revision', 'tokenizer', 'tokenizer_revision'):
            if getattr(model_config, field) != getattr(profile, field):
                raise ValueError('preregistered model metadata differs from profile')
        if cue.expires_at is not None and cue.expires_at <= self.clock():
            raise ValueError('candidate already expired')
        envelope = self.uncertainty_state(actor, task_type)
        candidate = uuid.uuid4().hex
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            self.engine._state(con, scope)
            self._uncertainty_recheck(con, actor, task_type, envelope)
            if con.execute('SELECT 1 FROM cce_versions WHERE tenant=? AND agent=? AND contract=? AND cue_id=? AND version=?',
                           (*scope, self.engine.contract, cue.cue_id, cue.version)).fetchone():
                raise ValueError('cue identity/version already registered; create a new version')
            con.execute('INSERT INTO cce_versions VALUES(?,?,?,?,?,?,?)',
                        (*scope, self.engine.contract, cue.cue_id, cue.version, cue.content_hash, candidate))
            if reservation is None:
                reservation = self._reserve(con, scope, manifest)
            else:
                registered = con.execute('SELECT manifest,status FROM cce_studies WHERE id=? AND tenant=? AND agent=? AND contract=?',
                    (reservation, *scope, self.engine.contract)).fetchone()
                if registered is None or registered['status'] != 'reserved' or registered['manifest'] != _json(asdict(manifest)):
                    raise ValueError('fresh matching scoped study reservation required')
            con.execute('INSERT INTO cce_candidates VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                (candidate, *scope, self.engine.contract, _json(asdict(cue)), _json(asdict(profile)),
                 task_type, generator_id, _json({'dataset': asdict(manifest),
                    'model_config': asdict(model_config)}), None, 'pending', None))
            con.execute("UPDATE cce_studies SET status='consumed' WHERE id=?", (reservation,))
            self.engine._event(con, scope, 'cce_proposed', {'candidate': candidate, 'cue_hash': cue.content_hash})
        return candidate

    def evaluate(self, actor, candidate, pairs, *, evaluator_id, accepted=True):
        """Trusted independent evaluator supplies scored, provider-bound receipts.

        No model-supplied booleans are accepted by a network endpoint. The host
        authenticates the evaluator before issuing this existing capability.
        """
        scope = self._scope(actor, 'evaluator')
        _id(evaluator_id)
        from .cue_evaluation import DatasetManifest
        context = self.status(actor, candidate)['task_type']
        envelope = self.uncertainty_state(actor, context, require_learning=True)
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            row = self._row(con, scope, candidate)
            self._uncertainty_recheck(con, actor, context, envelope)
            if row['status'] != 'pending':
                raise ValueError('candidate can be evaluated only once')
            cue = Cue(**json.loads(row['cue']))
            profile = ModelProfile(**json.loads(row['profile']))
            registered = json.loads(row['manifest'])
            report = evaluate_pairs(candidate, DatasetManifest(**registered['dataset']), pairs,
                profile_key=profile.key, cue_digest=cue.content_hash, task_type=row['task_type'])
            # A self-declared profile hash cannot disguise changed provider IDs.
            model = report.pairs[0].baseline.model
            if asdict(model) != registered['model_config']:
                raise ValueError('inference configuration differs from preregistered experiment')
            for field in ('provider', 'model', 'revision', 'tokenizer', 'tokenizer_revision'):
                if getattr(model, field) != getattr(profile, field):
                    raise ValueError('observation model metadata differs from registered profile')
            receipt = IndependentReceipt(evaluator_id, candidate, report.digest, accepted)
            decision = promotion_decision(report, (receipt,), generator_id=row['generator'])
            stored = {'report': report.to_dict(), 'metrics': report.metrics,
                      'receipt': asdict(receipt), 'decision': decision.to_dict()}
            con.execute('UPDATE cce_candidates SET report=?,status=?,expires=? WHERE id=?',
                (_json(stored), 'passed' if decision.eligible else 'rejected', self.clock() + 604800, candidate))
            self.engine._event(con, scope, 'cce_evaluated', {'candidate': candidate,
                'report_digest': report.digest, 'eligible': decision.eligible, 'reasons': list(decision.reasons)})
        return stored

    def reject_pending(self, actor, candidate, *, reason):
        """Seal a failed/aborted study so it cannot be resumed against its holdout."""
        scope = self._scope(actor, 'evaluator')
        _id(reason)
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            row = self._row(con, scope, candidate)
            if row['status'] != 'pending':
                raise ValueError('only pending experiments may be rejected')
            con.execute("UPDATE cce_candidates SET status='rejected' WHERE id=?", (candidate,))
            self.engine._event(con, scope, 'cce_rejected', {'candidate': candidate, 'reason': reason})

    def activate(self, actor, candidate, *, expected_generation, reason, valid_for=86400):
        scope = self._scope(actor, 'operator')
        self.engine._approval_input(expected_generation, reason)
        if type(valid_for) not in (int, float) or not math.isfinite(valid_for) or not 0 < valid_for <= 604800:
            raise ValueError('approval lifetime must be at most seven days')
        context = self.status(actor, candidate)['task_type']
        envelope = self.uncertainty_state(actor, context, require_learning=True)
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            row = self._row(con, scope, candidate)
            self._uncertainty_recheck(con, actor, context, envelope)
            cue = Cue(**json.loads(row['cue']))
            if row['status'] != 'passed' or safety_reason(cue):
                raise PermissionError('independently passed candidate required')
            if row['task_type'].lower() in ('clinical', 'medical', 'diagnosis', 'treatment'):
                raise PermissionError('clinical cues remain disabled')
            expires = min(self.clock() + valid_for, cue.expires_at or float('inf'), row['expires'])
            if expires <= self.clock():
                raise ValueError('cue expired; fresh evidence required')
            key = (*scope, self.engine.contract, row['task_type'], cue.profile_key)
            route = con.execute('SELECT generation FROM cce_routes WHERE tenant=? AND agent=? AND contract=? AND task_type=? AND profile=?', key).fetchone()
            generation = route['generation'] if route else 0
            if generation != expected_generation:
                raise ValueError('stale cue generation')
            con.execute('INSERT OR REPLACE INTO cce_routes VALUES(?,?,?,?,?,?,?)', (*key, candidate, generation + 1))
            con.execute("UPDATE cce_candidates SET status='approved',expires=? WHERE id=?", (expires, candidate))
            self.engine._event(con, scope, 'cce_approved', {'candidate': candidate, 'generation': generation + 1, 'review': reason})
        return {'candidate': candidate, 'generation': generation + 1, 'expires': expires}

    def revoke(self, actor, candidate, *, reason):
        scope = self._scope(actor, 'operator')
        self.engine._approval_input(0, reason)
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            self._row(con, scope, candidate)
            con.execute("UPDATE cce_candidates SET status='revoked' WHERE id=?", (candidate,))
            con.execute('UPDATE cce_routes SET active=NULL,generation=generation+1 WHERE active=?', (candidate,))
            self.engine._event(con, scope, 'cce_revoked', {'candidate': candidate, 'review': reason})

    def select(self, actor, profile, task_type, *, risk='low', clinical=False, permission_granted=False):
        scope = self._scope(actor, 'runtime')
        if not isinstance(profile, ModelProfile):
            raise TypeError('exact model profile required')
        _id(task_type)
        envelope = self.uncertainty_state(actor, task_type, require_learning=True)
        registry = CueRegistry()
        with self.engine._db() as con:
            self.engine._state(con, scope)
            self._uncertainty_recheck(con, actor, task_type, envelope)
            route = con.execute('SELECT active FROM cce_routes WHERE tenant=? AND agent=? AND contract=? AND task_type=? AND profile=?',
                (*scope, self.engine.contract, task_type, profile.key)).fetchone()
            if route and route['active']:
                row = self._row(con, scope, route['active'])
                if row['status'] == 'approved' and row['expires'] > self.clock():
                    cue = Cue(**json.loads(row['cue']))
                    registry.register(cue)
                    registry.approve(cue.cue_id, cue.version, approval_id=row['id'])
            selection = CueRouter(registry, enabled=self.enabled, clock=self.clock).select(profile, task_type,
                risk=risk, clinical=clinical, permission_granted=permission_granted)
            self.engine._event(con, scope, 'cce_selected', selection.telemetry())
        return selection

    def route_status(self, actor, profile, task_type):
        scope = self._scope(actor, 'auditor', 'operator', 'runtime')
        if not isinstance(profile, ModelProfile):
            raise TypeError('exact model profile required')
        _id(task_type)
        with self.engine._db() as con:
            self.engine._state(con, scope)
            row = con.execute('SELECT active,generation FROM cce_routes WHERE tenant=? AND agent=? AND contract=? AND task_type=? AND profile=?',
                (*scope, self.engine.contract, task_type, profile.key)).fetchone()
        return dict(row) if row else {'active': None, 'generation': 0}

    def feedback(self, actor, candidate, *, episode_id, safe, correct):
        """Independent host outcomes invalidate bad cues, never auto-promote."""
        scope = self._scope(actor, 'evaluator')
        _id(episode_id)
        if type(safe) is not bool or type(correct) is not bool:
            raise ValueError('independently judged boolean outcomes required')
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            self._row(con, scope, candidate)
            con.execute('INSERT INTO cce_feedback VALUES(?,?,?,?)', (candidate, episode_id, safe, correct))
            if not safe or not correct:
                con.execute("UPDATE cce_candidates SET status='revoked' WHERE id=?", (candidate,))
                con.execute('UPDATE cce_routes SET active=NULL,generation=generation+1 WHERE active=?', (candidate,))
            self.engine._event(con, scope, 'cce_feedback', {'candidate': candidate, 'episode': episode_id,
                'safe': safe, 'correct': correct, 'invalidated': not safe or not correct})

    def status(self, actor, candidate):
        scope = self._scope(actor, 'auditor', 'operator', 'evaluator', 'trainer')
        with self.engine._db() as con:
            row = self._row(con, scope, candidate)
        return {'candidate': row['id'], 'status': row['status'], 'task_type': row['task_type'],
                'expires': row['expires'], 'evaluation': json.loads(row['report']) if row['report'] else None}

    def export_memory(self, actor, candidate, ledger, memory_actor):
        """Add aggregate research evidence to existing memory as a pending record."""
        scope = self._scope(actor, 'auditor', 'operator')
        if scope != (memory_actor.tenant_id, memory_actor.agent_id):
            raise PermissionError('memory scope differs from cue scope')
        status = self.status(actor, candidate)
        envelope = self.uncertainty_state(actor, status['task_type'])
        from .uncertainty.adapters import memory_boundary
        memory_boundary(ledger, memory_actor, 'cognitive-cues', self.uncertainty)
        if envelope is not None:
            self.uncertainty.match_memory_actor(memory_actor)
            envelope = self.uncertainty.handoff(memory_actor, envelope)
            status['uncertainty'] = envelope
            status['guidance_authority'] = False
        report = status.pop('evaluation')
        status['report_digest'] = report['decision']['report_digest'] if report else None
        status['note'] = 'Research evidence only; memory cannot authorize cue deployment.'
        return ledger.propose(memory_actor, context='cognitive-cues', content=_json(status),
                              source_id=candidate, kind='episodic')
