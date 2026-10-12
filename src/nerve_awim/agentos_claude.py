"""Optional text-only reviewer with a persistent $25 task budget.

The caller supplies the API key and owns the single task ledger path. Unknown
charges consume their full reservation and stop further requests, across restart.
"""
import os
from pathlib import Path
import sqlite3

from .claude_pilot import (INPUT_RATE, MAX_OUTPUT, MODEL, OUTPUT_RATE,
                           RESERVATION, PilotError, post_message)

BUDGET = 25_000_000
MAX_CALLS = 120


class ClaudeReviewer:
    def __init__(self, path, key=None, *, send=post_message):
        self.path = str(Path(path))
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(fd)
        self._key, self._send = key, send
        with sqlite3.connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('CREATE TABLE IF NOT EXISTS reviewer_config '
                       '(id INTEGER PRIMARY KEY CHECK(id=1), budget INTEGER, halted INTEGER)')
            db.execute('INSERT OR IGNORE INTO reviewer_config VALUES(1,?,0)', (BUDGET,))
            db.execute('CREATE TABLE IF NOT EXISTS reviewer_calls '
                       '(id INTEGER PRIMARY KEY, reserved INTEGER NOT NULL, actual INTEGER, status TEXT NOT NULL)')
            if db.execute('SELECT budget FROM reviewer_config WHERE id=1').fetchone()[0] != BUDGET:
                raise PilotError('reviewer budget configuration mismatch')

    @staticmethod
    def _validated(response):
        if type(response) is not dict or response.get('model') != MODEL:
            raise PilotError('unexpected reviewer response')
        usage = response.get('usage')
        if type(usage) is not dict:
            raise PilotError('missing reviewer usage')
        inp, out = usage.get('input_tokens'), usage.get('output_tokens')
        if (type(inp) is not int or type(out) is not int
                or not 0 <= inp <= 1_000_000 or not 0 <= out <= MAX_OUTPUT):
            raise PilotError('unexpected reviewer token usage')
        for name, value in usage.items():
            if name in ('input_tokens', 'output_tokens'):
                continue
            if name in ('cache_creation_input_tokens', 'cache_read_input_tokens'):
                valid = type(value) is int and value == 0
            elif name in ('cache_creation', 'server_tool_use'):
                allowed = ({'ephemeral_5m_input_tokens', 'ephemeral_1h_input_tokens'}
                           if name == 'cache_creation' else {'web_search_requests', 'web_fetch_requests'})
                valid = value is None or (type(value) is dict and set(value) <= allowed
                         and all(type(v) is int and v == 0 for v in value.values()))
            elif name == 'service_tier':
                valid = value == 'standard'
            elif name == 'inference_geo':
                valid = value == 'global'
            else:
                valid = False
            if not valid:
                raise PilotError('unsupported reviewer billing metadata')
        blocks = response.get('content')
        if (response.get('stop_reason') != 'end_turn' or type(blocks) is not list or not blocks
                or any(type(b) is not dict or b.get('type') != 'text'
                       or type(b.get('text')) is not str for b in blocks)):
            raise PilotError('complete text-only reviewer response required')
        text = ''.join(b['text'] for b in blocks)
        if not text or len(text.encode()) > 131072:
            raise PilotError('bounded reviewer response required')
        return text, inp * INPUT_RATE + out * OUTPUT_RATE

    def complete(self, system, prompt):
        if type(self._key) is not str or not self._key.strip():
            raise PilotError('Claude API key required; no request reserved')
        if (type(system) is not str or type(prompt) is not str
                or len((system + prompt).encode()) > 24000):
            raise PilotError('bounded text-only request required')
        with sqlite3.connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            halted = db.execute('SELECT halted FROM reviewer_config WHERE id=1').fetchone()[0]
            count, committed, uncertain = db.execute('SELECT COUNT(*),COALESCE(SUM(reserved),0),'
                "COALESCE(SUM(status!='completed'),0) FROM reviewer_calls").fetchone()
            if halted or uncertain:
                raise PilotError('reviewer halted or request unresolved; no automatic retry')
            if count >= MAX_CALLS or committed + RESERVATION > BUDGET:
                raise PilotError('reviewer task budget exhausted')
            call = db.execute("INSERT INTO reviewer_calls(reserved,status) VALUES(?,'pending')",
                              (RESERVATION,)).lastrowid
        try:
            response = self._send(self._key, dict(model=MODEL, system=system,
                messages=[dict(role='user', content=prompt)], max_tokens=MAX_OUTPUT,
                service_tier='standard_only'))
            text, actual = self._validated(response)
            with sqlite3.connect(self.path) as db:
                db.execute('UPDATE reviewer_calls SET reserved=?,actual=?,status=? WHERE id=?',
                           (actual, actual, 'completed', call))
            return text
        except Exception:
            with sqlite3.connect(self.path) as db:
                db.execute('UPDATE reviewer_config SET halted=1 WHERE id=1')
                db.execute("UPDATE reviewer_calls SET status='uncertain' WHERE id=? AND status='pending'", (call,))
            # Transport/mocks may contain credentials in their exceptions.
            raise PilotError('Claude reviewer halted; see sanitized budget report') from None

    def report(self):
        with sqlite3.connect(self.path) as db:
            count, reserved, actual, uncertain = db.execute('SELECT COUNT(*),COALESCE(SUM(reserved),0),'
                "COALESCE(SUM(actual),0),COALESCE(SUM(status!='completed'),0) FROM reviewer_calls").fetchone()
        return dict(budget_usd=BUDGET/1e6, accounted_usd=reserved/1e6,
                    confirmed_usage_cost_usd=actual/1e6, uncertain_calls=uncertain,
                    model=MODEL, calls=count)
