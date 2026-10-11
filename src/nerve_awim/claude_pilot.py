"""Single-process pilot transport with durable, fail-closed dollar reservation."""
import json
import os
import sqlite3
import urllib.request
import urllib.error

MODEL = 'claude-sonnet-4-6'
# USD microdollars/token, standard global pricing checked 2026-10-11.
INPUT_RATE, OUTPUT_RATE = 3, 15
MAX_OUTPUT = 1024
# Reserve the entire supported 1M input context before every request. Refund
# only after a complete response with validated usage; uncertain calls abort.
RESERVATION = 1_000_000 * INPUT_RATE + MAX_OUTPUT * OUTPUT_RATE


class PilotError(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise PilotError('redirect refused')


def post_message(key, body):
    request = urllib.request.Request('https://api.anthropic.com/v1/messages',
        data=json.dumps(body).encode(), headers={'x-api-key': key,
        'anthropic-version': '2023-06-01', 'content-type': 'application/json'})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=60) as response:
            data = response.read(131073)
        if len(data) > 131072:
            raise PilotError('response too large')
        return json.loads(data)
    except urllib.error.HTTPError as error:
        raise PilotError('Claude HTTP ' + str(error.code)) from None
    except Exception:
        # Never propagate provider bodies, request headers or credentials.
        raise PilotError('Claude request failed; no automatic retry') from None


class ClaudePilot:
    def __init__(self, path, key, *, send=post_message):
        if not key:
            raise PilotError('missing Claude repository secret')
        # A fresh exclusive ledger is mandatory; do not reset a spent ledger.
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        self.path, self._key, self._send = path, key, send
        self.failed = False
        with sqlite3.connect(path) as con:
            con.execute('CREATE TABLE calls (id INTEGER PRIMARY KEY, reserved INTEGER, actual INTEGER, status TEXT)')

    def complete(self, system, prompt):
        if self.failed:
            raise PilotError('pilot halted after failure')
        if type(system) is not str or type(prompt) is not str or len((system + prompt).encode()) > 24000:
            raise PilotError('bounded text-only request required')
        with sqlite3.connect(self.path) as con:
            con.execute('BEGIN IMMEDIATE')
            count, committed = con.execute('SELECT COUNT(*),COALESCE(SUM(reserved),0) FROM calls').fetchone()
            if count >= 120 or committed + RESERVATION > 10_000_000:
                raise PilotError('pilot budget exhausted')
            call = con.execute('INSERT INTO calls(reserved,status) VALUES(?,?)', (RESERVATION, 'pending')).lastrowid
        try:
            response = self._send(self._key, {'model': MODEL, 'system': system,
                'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': MAX_OUTPUT})
            usage = response['usage']
            inp, out = usage['input_tokens'], usage['output_tokens']
            if type(inp) is not int or type(out) is not int or not 0 <= inp <= 1_000_000 or not 0 <= out <= MAX_OUTPUT:
                raise PilotError('unexpected token usage')
            if any(usage.get(k, 0) != 0 for k in ('cache_creation_input_tokens', 'cache_read_input_tokens')):
                raise PilotError('unexpected billable cache usage')
            actual = inp * INPUT_RATE + out * OUTPUT_RATE
            with sqlite3.connect(self.path) as con:
                con.execute('UPDATE calls SET reserved=?,actual=?,status=? WHERE id=?', (actual, actual, 'completed', call))
            if response['stop_reason'] != 'end_turn':
                raise PilotError('incomplete model output')
            blocks = response['content']
            if not blocks or any(b.get('type') != 'text' for b in blocks):
                raise PilotError('text-only response required')
            return ''.join(b['text'] for b in blocks)
        except PilotError:
            self.failed = True
            raise
        except Exception:
            self.failed = True
            raise PilotError('pilot halted; inspect sanitized budget report') from None

    def report(self):
        with sqlite3.connect(self.path) as con:
            count, reserved, actual, pending = con.execute('''SELECT COUNT(*),COALESCE(SUM(reserved),0),
                COALESCE(SUM(actual),0),SUM(status='pending') FROM calls''').fetchone()
        return {'model': MODEL, 'calls': count, 'budget_usd': 10,
                'accounted_usd': reserved/1e6, 'confirmed_usage_cost_usd': actual/1e6,
                'uncertain_calls': pending or 0, 'pricing_date': '2026-10-11'}
