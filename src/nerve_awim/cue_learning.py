"""CCE extension of NERVE's existing authority, SQLite ledger and audit stream.

This is a trusted local host API, not an authentication service. It cannot grant
tool permissions or clinical approval. Outcomes/receipts must come from trusted
host evaluators; SQL and host Python code are within the existing trust boundary.
"""
from dataclasses import asdict
from hashlib import sha256
import json
import math
import time
import uuid

from .cue_engine import Cue, CueRegistry, CueRouter, CueSelection, ModelProfile, safety_reason
from .cue_evaluation import (evaluate_pairs, promotion_decision, regression_decision,
    IndependentReceipt, ModelParity, DatasetManifest, EvaluationReport)
from .governed_learning_v20 import GovernedLearning, _id, _json


class GovernedCueCoordinator:
    def __init__(self, engine, *, enabled=False, clock=time.time):
        if not isinstance(engine, GovernedLearning) or type(enabled) is not bool or not callable(clock):
            raise TypeError('existing governed engine, explicit opt-in and clock required')
        self.engine, self.enabled, self.clock = engine, enabled, clock
        with engine._db() as con:
            con.executescript('''
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
              CREATE TABLE IF NOT EXISTS cce_regression_studies (
                reservation TEXT PRIMARY KEY, tenant TEXT, agent TEXT, contract TEXT, candidate TEXT);
              CREATE TABLE IF NOT EXISTS cce_regression_reports (
                candidate TEXT PRIMARY KEY, evidence TEXT);
              CREATE TABLE IF NOT EXISTS cce_dataset_studies (
                reservation TEXT PRIMARY KEY, tenant TEXT, agent TEXT, contract TEXT,
                dataset_digest TEXT, candidate TEXT);
              CREATE TABLE IF NOT EXISTS cce_dataset_fingerprints (
                tenant TEXT, agent TEXT, kind TEXT, fingerprint TEXT, split TEXT,
                reservation TEXT,
                PRIMARY KEY(tenant,agent,kind,fingerprint));
            ''')

    def _scope(self, actor, *roles):
        return self.engine._scope(actor, *roles)

    def _row(self, con, scope, candidate):
        self.engine._state(con, scope)
        row = con.execute('SELECT * FROM cce_candidates WHERE id=? AND tenant=? AND agent=? AND contract=?',
                          (candidate, *scope, self.engine.contract)).fetchone()
        if row is None:
            raise LookupError('cue candidate not available in current scope/contract')
        return row

    def _dataset_required(self, con, scope):
        return con.execute('SELECT 1 FROM cce_dataset_studies WHERE tenant=? AND agent=? LIMIT 1',
                           scope).fetchone() is not None

    def _candidate_dataset_valid(self, con, scope, candidate):
        return (not self._dataset_required(con, scope) or con.execute(
            'SELECT 1 FROM cce_dataset_studies WHERE candidate=? AND tenant=? AND agent=? AND contract=?',
            (candidate, *scope, self.engine.contract)).fetchone() is not None)

    def _regression_required(self, con, scope, row=None):
        return (bool(row and json.loads(row['manifest'])['dataset'].get('regression'))
                or con.execute('SELECT 1 FROM cce_regression_studies WHERE tenant=? AND agent=? LIMIT 1',
                               scope).fetchone() is not None)

    def _bound_report(self, row, pairs, *, split):
        cue = Cue(**json.loads(row['cue']))
        profile = ModelProfile(**json.loads(row['profile']))
        registered = json.loads(row['manifest'])
        report = evaluate_pairs(row['id'], DatasetManifest(**registered['dataset']), pairs,
            split=split, profile_key=profile.key, cue_digest=cue.content_hash, task_type=row['task_type'])
        model = report.pairs[0].baseline.model
        if asdict(model) != registered['model_config']:
            raise ValueError('inference configuration differs from preregistered experiment')
        for name in ('provider', 'model', 'revision', 'tokenizer', 'tokenizer_revision'):
            if getattr(model, name) != getattr(profile, name):
                raise ValueError('observation model metadata differs from registered profile')
        return report

    def _regression_evidence(self, con, candidate):
        row = con.execute('SELECT evidence FROM cce_regression_reports WHERE candidate=?', (candidate,)).fetchone()
        return json.loads(row['evidence']) if row else None

    def _candidate_regression_valid(self, con, scope, row):
        if not self._regression_required(con, scope, row):
            return True
        if not json.loads(row['manifest'])['dataset'].get('regression'):
            return False
        if con.execute('SELECT 1 FROM cce_regression_studies WHERE candidate=? AND tenant=? AND agent=? AND contract=?',
                       (row['id'], *scope, self.engine.contract)).fetchone() is None:
            return False
        try:
            stored = self._regression_evidence(con, row['id'])
            if type(stored) is not dict or set(stored) != {'report', 'metrics', 'receipt', 'decision'}:
                return False
            report = EvaluationReport.from_dict(stored['report'])
            checked = self._bound_report(row, report.pairs, split='regression')
            if checked != report:
                return False
            receipt = IndependentReceipt(**stored['receipt'])
            decision = regression_decision(checked, (receipt,), generator_id=row['generator'])
            return (decision.eligible and stored['metrics'] == checked.metrics
                    and _json(stored['decision']) == _json(decision.to_dict()))
        except (ValueError, TypeError, KeyError):
            return False

    def _reserve(self, con, scope, manifest, *, dataset_bound=False):
        if self._dataset_required(con, scope) and not dataset_bound:
            raise ValueError('dataset-bound scope cannot downgrade to ID-only reservations')
        if self._regression_required(con, scope) and not manifest.regression:
            raise ValueError('regression-bound scope cannot downgrade to regressionless reservations')
        reservation = uuid.uuid4().hex
        for split in ('discovery', 'selection', 'holdout', 'regression'):
            for task in getattr(manifest, split):
                previous = con.execute('SELECT split FROM cce_partitions WHERE tenant=? AND agent=? AND contract=? AND task=?',
                    (*scope, self.engine.contract, task)).fetchone()
                if previous and (previous['split'] != split or split == 'holdout'):
                    raise ValueError('reserved/previously used holdout or changed dataset split')
                con.execute('INSERT OR IGNORE INTO cce_partitions VALUES(?,?,?,?,?,?)',
                    (*scope, self.engine.contract, task, split, reservation))
        con.execute('INSERT INTO cce_studies VALUES(?,?,?,?,?,?)',
            (reservation, *scope, self.engine.contract, _json(manifest.to_dict()), 'reserved'))
        if manifest.regression:
            con.execute('INSERT INTO cce_regression_studies VALUES(?,?,?,?,NULL)',
                        (reservation, *scope, self.engine.contract))
        return reservation

    def reserve_dataset(self, actor, dataset):
        """Persist content/family protection before callbacks, across contract revisions.

        Protection is scoped to tenant/agent. Historical ID-only studies cannot
        be reconstructed. Family labels are host declarations, not semantic proof.
        Once enabled for a scope, ID-only reservation paths cannot downgrade it.
        """
        from .cue_dataset import validate_dataset
        scope = self._scope(actor, 'trainer')
        dataset = validate_dataset(dataset)
        identities = set()
        for task_id, family, split in dataset.families:
            identities.add(('family', sha256(family.encode()).hexdigest(), split))
        for split in ('discovery', 'selection', 'holdout', 'regression'):
            for task in getattr(dataset, split + '_tasks'):
                identities.add(('content', sha256(task.instruction.strip().encode()).hexdigest(), split))
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            self.engine._state(con, scope)
            for kind, fingerprint, split in identities:
                previous = con.execute('SELECT split FROM cce_dataset_fingerprints WHERE tenant=? AND agent=? AND kind=? AND fingerprint=?',
                    (*scope, kind, fingerprint)).fetchone()
                if previous and (previous['split'] != split or split == 'holdout'):
                    raise ValueError('reserved content/family reused or moved between splits')
            reservation = self._reserve(con, scope, dataset.manifest, dataset_bound=True)
            con.execute('INSERT INTO cce_dataset_studies VALUES(?,?,?,?,?,NULL)',
                (reservation, *scope, self.engine.contract, dataset.digest))
            for kind, fingerprint, split in identities:
                con.execute('INSERT OR IGNORE INTO cce_dataset_fingerprints VALUES(?,?,?,?,?,?)',
                    (*scope, kind, fingerprint, split, reservation))
            self.engine._event(con, scope, 'cce_dataset_reserved',
                {'reservation': reservation, 'dataset_digest': dataset.digest,
                 'counts': dataset.telemetry()['counts']})
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
        candidate = uuid.uuid4().hex
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            self.engine._state(con, scope)
            if self._regression_required(con, scope) and not manifest.regression:
                raise ValueError('regression-bound scope requires regression-bearing proposal')
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
                if registered is None or registered['status'] != 'reserved' or DatasetManifest(**json.loads(registered['manifest'])) != manifest:
                    raise ValueError('fresh matching scoped study reservation required')
                if self._dataset_required(con, scope) and con.execute(
                        'SELECT 1 FROM cce_dataset_studies WHERE reservation=? AND tenant=? AND agent=? AND contract=?',
                        (reservation, *scope, self.engine.contract)).fetchone() is None:
                    raise ValueError('dataset-bound scope requires matching dataset reservation')
                if manifest.regression and con.execute(
                        'SELECT 1 FROM cce_regression_studies WHERE reservation=? AND tenant=? AND agent=? AND contract=? AND candidate IS NULL',
                        (reservation, *scope, self.engine.contract)).fetchone() is None:
                    raise ValueError('regression-bound proposal requires matching reservation')
            con.execute('INSERT INTO cce_candidates VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                (candidate, *scope, self.engine.contract, _json(asdict(cue)), _json(asdict(profile)),
                 task_type, generator_id, _json({'dataset': manifest.to_dict(),
                    'model_config': asdict(model_config)}), None, 'pending', None))
            con.execute("UPDATE cce_studies SET status='consumed' WHERE id=?", (reservation,))
            con.execute('UPDATE cce_regression_studies SET candidate=? WHERE reservation=?',
                        (candidate, reservation))
            con.execute('UPDATE cce_dataset_studies SET candidate=? WHERE reservation=?',
                        (candidate, reservation))
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
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            row = self._row(con, scope, candidate)
            if not self._candidate_dataset_valid(con, scope, candidate):
                raise PermissionError('dataset-bound evidence required after scope upgrade')
            if row['status'] != 'pending':
                raise ValueError('candidate can be evaluated only once')
            if not self._candidate_regression_valid(con, scope, row):
                raise PermissionError('successful bound regression evidence required before holdout')
            report = self._bound_report(row, pairs, split='holdout')
            receipt = IndependentReceipt(evaluator_id, candidate, report.digest, accepted)
            decision = promotion_decision(report, (receipt,), generator_id=row['generator'])
            stored = {'report': report.to_dict(), 'metrics': report.metrics,
                      'receipt': asdict(receipt), 'decision': decision.to_dict()}
            con.execute('UPDATE cce_candidates SET report=?,status=?,expires=? WHERE id=?',
                (_json(stored), 'passed' if decision.eligible else 'rejected', self.clock() + 604800, candidate))
            self.engine._event(con, scope, 'cce_evaluated', {'candidate': candidate,
                'report_digest': report.digest, 'eligible': decision.eligible, 'reasons': list(decision.reasons)})
        return stored

    def evaluate_regression(self, actor, candidate, pairs, *, evaluator_id, accepted=True):
        """Persist one independently attested retained-capability gate before holdout."""
        scope = self._scope(actor, 'evaluator')
        _id(evaluator_id)
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            row = self._row(con, scope, candidate)
            if not self._candidate_dataset_valid(con, scope, candidate):
                raise PermissionError('dataset-bound evidence required after scope upgrade')
            if row['status'] != 'pending' or self._regression_evidence(con, candidate) is not None:
                raise ValueError('regression can be evaluated once for a pending candidate')
            if (not json.loads(row['manifest'])['dataset'].get('regression') or con.execute(
                    'SELECT 1 FROM cce_regression_studies WHERE candidate=? AND tenant=? AND agent=? AND contract=?',
                    (candidate, *scope, self.engine.contract)).fetchone() is None):
                raise PermissionError('preregistered bound regression partition required')
            report = self._bound_report(row, pairs, split='regression')
            receipt = IndependentReceipt(evaluator_id, candidate, report.digest, accepted)
            decision = regression_decision(report, (receipt,), generator_id=row['generator'])
            stored = {'report': report.to_dict(), 'metrics': report.metrics,
                      'receipt': asdict(receipt), 'decision': decision.to_dict()}
            con.execute('INSERT INTO cce_regression_reports VALUES(?,?)', (candidate, _json(stored)))
            if not decision.eligible:
                con.execute("UPDATE cce_candidates SET status='rejected' WHERE id=?", (candidate,))
            self.engine._event(con, scope, 'cce_regression_evaluated', {'candidate': candidate,
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
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            row = self._row(con, scope, candidate)
            cue = Cue(**json.loads(row['cue']))
            if row['status'] != 'passed' or safety_reason(cue):
                raise PermissionError('independently passed candidate required')
            if not self._candidate_dataset_valid(con, scope, candidate):
                raise PermissionError('dataset-bound evidence required after scope upgrade')
            if not self._candidate_regression_valid(con, scope, row):
                raise PermissionError('successful bound regression evidence required for activation')
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
        registry = CueRegistry()
        with self.engine._db() as con:
            self.engine._state(con, scope)
            route = con.execute('SELECT active FROM cce_routes WHERE tenant=? AND agent=? AND contract=? AND task_type=? AND profile=?',
                (*scope, self.engine.contract, task_type, profile.key)).fetchone()
            if route and route['active']:
                row = self._row(con, scope, route['active'])
                if (row['status'] == 'approved' and row['expires'] > self.clock()
                        and self._candidate_dataset_valid(con, scope, row['id'])
                        and self._candidate_regression_valid(con, scope, row)):
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
            dataset = con.execute('SELECT dataset_digest FROM cce_dataset_studies WHERE candidate=? AND tenant=? AND agent=? AND contract=?',
                                  (candidate, *scope, self.engine.contract)).fetchone()
            regression_status = {'required': self._regression_required(con, scope, row),
                                 'evaluation': self._regression_evidence(con, candidate)}
            dataset_status = {'required': self._dataset_required(con, scope),
                              'bound': dataset is not None,
                              'digest': dataset['dataset_digest'] if dataset else None}
        return {'candidate': row['id'], 'status': row['status'], 'task_type': row['task_type'],
                'dataset': dataset_status, 'regression': regression_status,
                'profile_key': ModelProfile(**json.loads(row['profile'])).key,
                'generator_id': row['generator'],
                'expires': row['expires'], 'evaluation': json.loads(row['report']) if row['report'] else None}

    def export_memory(self, actor, candidate, ledger, memory_actor):
        """Add aggregate research evidence to existing memory as a pending record."""
        scope = self._scope(actor, 'auditor', 'operator')
        if scope != (memory_actor.tenant_id, memory_actor.agent_id):
            raise PermissionError('memory scope differs from cue scope')
        status = self.status(actor, candidate)
        report = status.pop('evaluation')
        regression = status['regression'].pop('evaluation')
        status['regression']['report_digest'] = regression['decision']['report_digest'] if regression else None
        status['report_digest'] = report['decision']['report_digest'] if report else None
        status['note'] = 'Research evidence only; memory cannot authorize cue deployment.'
        return ledger.propose(memory_actor, context='cognitive-cues', content=_json(status),
                              source_id=candidate, kind='episodic')
