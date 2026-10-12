"""Evidence-derived output surfaces; a generated status cannot close a conflict."""
import json
from pathlib import Path
from .policy import relevant
from .propagation import Propagator
from .reconciliation import normalized, usable


def claim_text(claim):
    value = normalized(claim)[0] if type(claim.normalized_value) is bool else claim.normalized_value
    negation = 'not ' if type(value) is not bool and not claim.polarity else ''
    return claim.predicate + ': ' + negation + json.dumps(value, sort_keys=True, allow_nan=False) + (' ' + claim.units if claim.units else '')


class OutputGuard:
    def __init__(self, ledger, policy):
        self.ledger, self.policy = ledger, policy
        self.propagator = Propagator(ledger)

    def _validate(self, actor, task_id, conclusions, assessments):
        if type(conclusions) is not list or len(conclusions) > 128:
            raise ValueError('bounded conclusion list required')
        known = {c.claim_id: c for c in self.ledger.claims(actor, task_id)}
        clean = []
        for value in conclusions:
            if type(value) is not dict or set(value) - {'claim_id', 'text', 'dependency_claim_ids', 'decision_id'}:
                raise ValueError('unsupported generated conclusion fields')
            claim = known.get(value.get('claim_id'))
            if claim is None: raise ValueError('invented or inaccessible conclusion claim')
            ids = value.get('dependency_claim_ids', [])
            if type(ids) is not list or not set(ids) <= set(known):
                raise ValueError('invented dependency claims')
            deps = set(ids) | {claim.claim_id}
            if value.get('decision_id'):
                assessment = self.policy.get(actor, value['decision_id'], task_id=task_id)
                deps.update(assessment.dependency_claim_ids)
            if value.get('text', claim_text(claim)) != claim_text(claim):
                raise ValueError('unsupported prose cannot override structured source claim')
            clean.append({'claim_id': claim.claim_id, 'dependency_claim_ids': sorted(deps),
                          'text': claim_text(claim), 'decision_id': value.get('decision_id')})
        return clean

    def render(self, actor, task_id, conclusions, assessments=(), regenerate=None):
        # At most one repair, then a deterministic source-linked partial response.
        repair_count, fallback = 0, False
        try:
            clean = self._validate(actor, task_id, conclusions, assessments)
        except (ValueError, LookupError, PermissionError, TypeError):
            clean = None
            if regenerate is not None:
                repair_count = 1
                try:
                    proposed = regenerate({'issues': ['Use current scoped claim IDs and exact source-linked values; preserve open conflicts']})
                    clean = self._validate(actor, task_id, proposed, assessments)
                except Exception:
                    clean = None
            if clean is None:
                fallback = True
                known = {c.claim_id: c for c in self.ledger.claims(actor, task_id)}
                requested = conclusions if type(conclusions) is list else []
                clean = []
                for value in requested:
                    if type(value) is not dict or type(value.get('claim_id')) is not str or value['claim_id'] not in known: continue
                    cid = value['claim_id']
                    raw_deps = value.get('dependency_claim_ids', [])
                    deps = {d for d in raw_deps if type(d) is str and d in known} if type(raw_deps) is list else set()
                    deps.add(cid)
                    decision_id = value.get('decision_id')
                    if decision_id:
                        try: deps.update(self.policy.get(actor, decision_id, task_id=task_id).dependency_claim_ids)
                        except (PermissionError, LookupError): decision_id = None
                    clean.append({'claim_id': cid, 'dependency_claim_ids': sorted(deps), 'text': claim_text(known[cid]), 'decision_id': decision_id})

        revision = self.ledger.revision(actor, task_id)
        conflicts = self.ledger.open_conflicts(actor, task_id)
        claims = {c.claim_id: c for c in self.ledger.claims(actor, task_id)}
        supported, qualified, unavailable = [], [], []
        for value in clean:
            claim = claims[value['claim_id']]
            try:
                self.ledger.source(actor, claim.source_ref, claim.source_revision)
                for cid in value['dependency_claim_ids']:
                    dependency = claims[cid]
                    self.ledger.source(actor, dependency.source_ref, dependency.source_revision)
                missing = any(not usable(claims[cid], self.policy.clock()) for cid in value['dependency_claim_ids'])
            except (PermissionError, LookupError):
                missing = True
            affected = [c.conflict_id for c in conflicts if relevant(c, value.get('decision_id'), value['dependency_claim_ids'])]
            item = {**value, 'source_refs': [claim.source_ref]}
            if missing:
                qualified.append({**item, 'qualification': 'Evidence unavailable, unknown, or outside its applicability interval', 'conflict_ids': affected})
                unavailable.append(claim.claim_id)
            elif affected:
                qualified.append({**item, 'qualification': 'Disputed; do not treat as confirmed', 'conflict_ids': affected})
            else:
                supported.append(item)
        unresolved = [{'conflict_id': c.conflict_id, 'affected_conclusion': c.claim_ids,
                       'status': c.status, 'evidence_refs': c.claim_ids,
                       'completed_checks': c.checks,
                       'next_check': 'Obtain independent current evidence or authorized evidence-backed review'}
                      for c in conflicts]
        actions = []
        for supplied in assessments:
            ident = supplied if type(supplied) is str else supplied.decision_id
            record = self.policy.get(actor, ident, task_id=task_id)
            stale = record.ledger_revision != revision or record.expires_at <= self.policy.clock()
            actions.append({'decision_assessment_id': ident,
                'decision_status': 'unavailable' if stale else record.status,
                'action_ids': record.permitted_action_ids if not stale else [],
                'blocked_action_ids': record.blocked_action_ids if not stale else record.permitted_action_ids + record.blocked_action_ids})
        if self.ledger.revision(actor, task_id) != revision:
            qualified.extend({**item, 'qualification': 'Evidence changed during rendering; reassess', 'conflict_ids': []} for item in supported)
            supported = []
            unavailable.append('ledger_changed')
            with self.ledger.engine._db() as con:
                con.execute('BEGIN')
                revision = self.ledger.revision(actor, task_id, con=con)
                latest = self.ledger.open_conflicts(actor, task_id, con=con)
            unresolved = [{'conflict_id': c.conflict_id, 'affected_conclusion': c.claim_ids,
                           'status': c.status, 'evidence_refs': c.claim_ids, 'completed_checks': c.checks,
                           'next_check': 'Refresh assessment using the changed evidence'} for c in latest]
            for action in actions:
                action['decision_status'] = 'unavailable'
                action['action_ids'] = []
        result = {'schema_version': 'uncertainty-result-v1', 'supported': supported,
                  'qualified': qualified, 'unresolved': unresolved, 'actions': actions,
                  'uncertainty_state_revision': revision, 'unavailable': unavailable,
                  'repair_count': repair_count, 'deterministic_fallback': fallback}
        parts = [v['text'] for v in supported]
        parts += [v['text'] + ' — ' + v['qualification'] for v in qualified]
        parts += ['Unresolved ' + v['conflict_id'] + ': ' + v['next_check'] for v in unresolved]
        if unavailable: parts.append('Verification unavailable for: ' + ', '.join(unavailable))
        result['text'] = '\n'.join(parts) or 'No supported conclusion available.'
        self.propagator.event(actor, task_id, 'output_validated', {'revision': revision,
            'open_conflicts': len(unresolved), 'supported': len(supported), 'qualified': len(qualified)})
        return result

    def save_report(self, path, actor, task_id, conclusions, **kwargs):
        result = self.render(actor, task_id, conclusions, **kwargs)
        Path(path).write_text(json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + '\n')
        return result

    def stream(self, actor, task_id, conclusions, **kwargs):
        # No generated prose or action status is emitted before hard validation.
        yield {'event': 'provisional', 'validated': False, 'message': 'Checking scoped evidence'}
        yield {'event': 'final', 'validated': True, 'result': self.render(actor, task_id, conclusions, **kwargs)}
