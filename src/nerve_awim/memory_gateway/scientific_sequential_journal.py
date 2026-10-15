"""Private transactional alpha wallet and paired betting gate.

For a fixed registered bet b, each discordant win multiplies E by 1+b,
each loss by 1-b, and ties by one. Under conditional P(win)<=1/2 this
is a nonnegative supermartingale. Fresh allocation is required across studies.
Only trusted evaluator outcomes enter this module; no deployment capability.
"""
from contextlib import contextmanager
import hmac
import json
import math
import os
from pathlib import Path
import sqlite3

from .scientific_sequential_contract import canonical, register, number


class IntegrityError(ValueError):
    pass


VERSION = 'loop40.2-journal-v1'


class Journal:
    def __init__(self, directory, *, key, total_alpha=.05, expected_ledger_head=None):
        if type(key) is not bytes or len(key) < 32:
            raise ValueError('host_integrity_key_required')
        number(total_alpha, 1e-12, .05)
        self.key = key
        self.root = Path(directory)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.root.is_symlink() or self.root.stat().st_mode & 0o077:
            raise ValueError('private_gate_directory_required')
        path = self.root / 'gate.sqlite'
        if path.is_symlink(): raise ValueError('no_symlink_database')
        fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600); os.close(fd)
        if path.stat().st_mode & 0o077: raise ValueError('private_database_required')
        self.db = sqlite3.connect(path, isolation_level=None, timeout=30)
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, body TEXT NOT NULL, mac TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS checkpoint (id INTEGER PRIMARY KEY CHECK(id=1), seq INTEGER NOT NULL, mac TEXT NOT NULL)')
        with self.transaction():
            events = self._events()
            if expected_ledger_head is not None and self.ledger_head() != expected_ledger_head:
                raise IntegrityError('degraded — integrity: trusted ledger head mismatch')
            if not events: self._append({'kind': 'wallet', 'total_alpha': total_alpha})
            elif events[0] != {'kind': 'wallet', 'total_alpha': total_alpha}:
                raise IntegrityError('degraded — integrity: wallet changed')

    def close(self): self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            self._verified_token = None
            raise

    def _token(self):
        return (self.db.total_changes, self.db.execute('PRAGMA data_version').fetchone()[0], self.key)

    def _events(self, *, force=False):
        token = self._token()
        if not force and getattr(self, '_verified_token', None) == token:
            return self._verified_events
        previous, events = '', []
        for index, (seq, body, mac) in enumerate(self.db.execute('SELECT seq,body,mac FROM events ORDER BY seq'), 1):
            expected = hmac.new(self.key, (previous + str(seq) + body).encode(), 'sha256').hexdigest()
            if seq != index or not hmac.compare_digest(mac, expected):
                raise IntegrityError('degraded — integrity: event history')
            previous = mac
            events.append(json.loads(body))
        checkpoint = self.db.execute('SELECT seq,mac FROM checkpoint WHERE id=1').fetchone()
        if (events and checkpoint != (len(events), previous)) or (not events and checkpoint):
            raise IntegrityError('degraded — integrity: truncated history')
        self._verified_events, self._verified_token = events, token
        return events

    def _append(self, event):
        events = self._events()
        last = self.db.execute('SELECT seq,mac FROM events ORDER BY seq DESC LIMIT 1').fetchone()
        seq, previous = (last[0] + 1, last[1]) if last else (1, '')
        body = canonical(event)
        mac = hmac.new(self.key, (previous + str(seq) + body).encode(), 'sha256').hexdigest()
        self.db.execute('INSERT INTO events VALUES (?,?,?)', (seq, body, mac))
        self.db.execute('INSERT OR REPLACE INTO checkpoint VALUES (1,?,?)', (seq, mac))
        self._verified_events = events + [json.loads(body)]
        self._verified_token = self._token()

    def start(self, registration):
        envelope = register(registration)
        # Deliberately staged: live holdout requires a separately reviewed/signed adapter.
        if registration['bank']['split'] == 'holdout':
            raise PermissionError('slice2_verdict_and_signed_live_gate_adapter_required')
        with self.transaction():
            events = self._events(force=True)
            studies = [e for e in events if e['kind'] == 'study']
            old = next((e for e in studies if e['registration']['study_id'] == registration['study_id']), None)
            event = dict(envelope, kind='study')
            if old:
                if old != event: raise IntegrityError('registration_changed')
                return envelope['sha256']
            spent = math.fsum(e['registration']['gate']['alpha'] for e in studies)
            if spent + registration['gate']['alpha'] > events[0]['total_alpha'] + 1e-15:
                raise PermissionError('alpha_wallet_exhausted')
            self._append(event)
        return envelope['sha256']

    def _study(self, study_id):
        events = self._events()
        studies = [e['registration'] for e in events if e['kind'] == 'study' and e['registration']['study_id'] == study_id]
        if len(studies) != 1: raise ValueError('registered_study_required')
        return studies[0], [e for e in events if e.get('study_id') == study_id]

    def claim(self, study_id, item_id, stratum):
        """Claim before inference. Interrupted claims are never dispatched again."""
        if not isinstance(item_id, str) or not item_id: raise ValueError('item_identity_required')
        with self.transaction():
            r, events = self._study(study_id)
            claims = [e for e in events if e['kind'] == 'claim']
            for claim in claims:
                if claim['item_id'] == item_id:
                    if claim['stratum'] != stratum: raise IntegrityError('item_stratum_changed')
                    return 'cached' if any(e['kind'] == 'outcome' and e['item_id'] == item_id for e in events) else 'incomplete_infrastructure'
            if any(e['kind'] == 'claim' and not any(o['kind'] == 'outcome' and o['item_id'] == e['item_id'] for o in events) for e in events):
                raise PermissionError('unresolved_claim_requires_recovery')
            if self._verdict(r, events)['verdict'] != 'running': raise PermissionError('terminal_study')
            if stratum not in r['gate']['strata']: raise ValueError('registered_stratum_required')
            # Bank identity scopes item identity; never re-use exposed items across proposals.
            for event in self._events():
                if event['kind'] == 'claim' and event['bank'] == r['bank']['manifest'] and event['item_id'] == item_id:
                    raise PermissionError('item_already_allocated')
            expected = r['schedule'][len(claims)]
            if expected != {'item_id': item_id, 'stratum': stratum}:
                raise ValueError('registered_item_order_required')
            self._append(dict(kind='claim', study_id=study_id, item_id=item_id, stratum=stratum, bank=r['bank']['manifest']))
        return 'dispatch_once'

    def record(self, study_id, item_id, *, candidate, incumbent, controls, violations):
        if type(candidate) is not bool or type(incumbent) is not bool or set(controls) != {'always_abstain', 'random'} or any(type(v) is not bool for v in controls.values()):
            raise ValueError('trusted_boolean_scores_required')
        if type(violations) is not list or any(type(v) is not str for v in violations): raise ValueError('verifier_labels_required')
        with self.transaction():
            r, events = self._study(study_id)
            claim = next((e for e in events if e['kind'] == 'claim' and e['item_id'] == item_id), None)
            if claim is None: raise PermissionError('claim_before_outcome_required')
            event = dict(kind='outcome', study_id=study_id, item_id=item_id, stratum=claim['stratum'],
                         candidate=candidate, incumbent=incumbent, controls=controls,
                         violations=violations)
            old = next((e for e in events if e['kind'] == 'outcome' and e['item_id'] == item_id), None)
            if old:
                if old != event: raise IntegrityError('outcome_changed')
                return
            self._append(event)

    def _verdict(self, registration, events):
        raise NotImplementedError('versioned_gate_required')

    def report(self, study_id):
        with self.transaction():
            r, events = self._study(study_id)
            return self._verdict(r, events)

    def ledger_head(self):
        self._events()
        row = self.db.execute('SELECT mac FROM events ORDER BY seq DESC LIMIT 1').fetchone()
        return row[0] if row else None
