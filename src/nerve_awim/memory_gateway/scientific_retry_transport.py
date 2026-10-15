"""Registered transport-only retries around the frozen cb65c81 v3 request builder.

The original transport builds/validates each logical response exactly once. This
adapter retries only socket/open/read timeouts, with an identical URL, method,
explicit headers and body. Never retries parser, authorization or HTTP errors.
"""
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import socket
import time
from types import SimpleNamespace
from urllib.error import URLError
from urllib.request import Request
from . import scientific_candidate_v3_study as dev

VERSION='scientific-v3-transport-policy-v2'
_BUSY=False


def policy():
    path=dev.pilot.ROOT/'docs/galahad/evidence/scientific-candidate-v3-study.json'
    raw=path.read_bytes(); report=json.loads(raw)
    if report['status']!='complete':raise ValueError('complete_development_evidence_required')
    current=dev.sources()
    if current!=report['protocol']['sources']:raise ValueError('cb65c81_policy_sources_changed')
    maxima={a:max(r['elapsed_seconds'] for r in report['rows'] if r['arm']==a and r['model_calls']) for a in ('baseline','candidate')}
    return dict(version=VERSION, model_policy_commit='cb65c81',
        development_receipt_sha256=sha256(raw).hexdigest(),
        latency_field='rows[].elapsed_seconds where model_calls=1; measured call intervals include host authorization overhead',
        latency_counts={'baseline':100,'candidate':60},max_latency_seconds=maxima,
        per_attempt_timeout_seconds={a:3*t for a,t in maxima.items()},
        max_attempts_per_logical_call=3,max_retries=2,retry_on='transport timeout only',
        request_rule='Same URL, HTTP method, explicit headers and exact body bytes for each attempt; first completed response only; no answer selection',
        journal_rule='Durable claimed row before each attempt; terminal status and elapsed time after each attempt; raw successful wire response private',
        caveat='A timed-out server request may continue computing; retry is not exactly-once server execution. Client attempts are counted separately.',
        model_digest=report['protocol']['expected_digest'])


def timeout_error(error):
    return isinstance(error,(TimeoutError,socket.timeout)) or isinstance(error,URLError) and isinstance(error.reason,(TimeoutError,socket.timeout))


def envelope(request):
    return dict(url=request.full_url,method=request.get_method(),headers=sorted(request.header_items()),body_hex=request.data.hex())


def fingerprint(value):return sha256(dev.canonical(value).encode()).hexdigest()


class RetryOpener:
    def __init__(self,opener,db,row_index,timeout,authorize,root):
        self.opener,self.db,self.row,self.timeout,self.authorize,self.root=opener,db,row_index,timeout,authorize,Path(root)

    def open(self,request,*,timeout):
        from .scientific_v3_holdout import write_once
        fixed=envelope(request);digest=fingerprint(fixed)
        self.db.execute('INSERT INTO requests VALUES(?,?,?)',(self.row,digest,dev.canonical(fixed)));self.db.commit()
        for attempt in range(3):
            self.authorize()
            clone=Request(fixed['url'],data=bytes.fromhex(fixed['body_hex']),method=fixed['method'],headers=dict(fixed['headers']))
            if fingerprint(envelope(clone))!=digest:raise ValueError('retry_request_changed')
            self.db.execute('INSERT INTO attempts VALUES(?,?,?,?,?,NULL)',(self.row,attempt,digest,'claimed',self.timeout));self.db.commit()
            tick=time.monotonic()
            try:
                with self.opener.open(clone,timeout=self.timeout) as response:raw=response.read(65537)
            except BaseException as error:
                timed=timeout_error(error)
                self.db.execute('UPDATE attempts SET status=?,elapsed=? WHERE row_index=? AND attempt=?',('timeout' if timed else 'error',time.monotonic()-tick,self.row,attempt));self.db.commit()
                if not timed or attempt==2:raise
                continue
            self.db.execute("UPDATE attempts SET status='complete',elapsed=? WHERE row_index=? AND attempt=?",(time.monotonic()-tick,self.row,attempt));self.db.commit()
            # Exact bytes retained even if original transport later rejects JSON/auth.
            write_once(self.root/f'private-wire-{self.row:03d}.json',dict(body_hex=raw.hex(),request_sha256=digest))
            return BytesIO(raw)
        raise AssertionError('bounded_attempt_loop')


def run(prepared,*,authorize,db,row_index,root,registered_policy):
    global _BUSY
    if _BUSY:raise RuntimeError('serial_transport_required')
    if registered_policy!=policy():raise ValueError('registered_transport_changed')
    if prepared['route']!='model':raise ValueError('model_route_required')
    timeout=registered_policy['per_attempt_timeout_seconds'][prepared['arm']]
    calibration=dev.transport.calibration; original=calibration._adapter
    actual=original(timeout)
    wrapped=SimpleNamespace(_opener=RetryOpener(actual._opener,db,row_index,timeout,authorize,root))
    def factory(requested):
        if requested!=30:raise ValueError('original_transport_contract_changed')
        return wrapped
    _BUSY=True;calibration._adapter=factory
    try:
        # Original policy, payload, output validation and post-response auth untouched.
        return dev.transport.run(prepared,authorize=authorize,timeout_seconds=30)
    finally:calibration._adapter=original;_BUSY=False
