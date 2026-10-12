"""Owner commands and isolated research demonstration; no deployment activation."""
import argparse
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import secrets
import stat
import sys
import time
from urllib.request import Request, build_opener, ProxyHandler
import uuid

from .client import RuntimeClient, MAX_BYTES, _NoRedirect
from .contracts import sign_owner_request


def owner_request(endpoint, secret, action, payload):
    checked = RuntimeClient(endpoint, 'endpoint-validation')
    nonce, timestamp = uuid.uuid4().hex, time.time()
    request = {'action': action, 'payload': payload, 'nonce': nonce, 'timestamp': timestamp,
               'signature': sign_owner_request(secret, action, payload, nonce, timestamp)}
    data = json.dumps(request, allow_nan=False).encode()
    if len(data) > MAX_BYTES:
        raise ValueError('bounded owner request required')
    with build_opener(ProxyHandler({}), _NoRedirect()).open(
            Request(checked.endpoint + '/owner', data=data,
                    headers={'Content-Type': 'application/json'}), timeout=3) as response:
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError('bounded owner response required')
        return json.loads(body)


def _owner_key(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'r') as source:
        info = os.fstat(source.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or
                info.st_mode & 0o077 or not 32 <= info.st_size <= 4096):
            raise PermissionError('private owner-owned regular key file required')
        key = source.read(4097).strip()
        if not 32 <= len(key) <= 4096:
            raise ValueError('bounded owner key required')
        return key


def _demo_service(connection, database, owner, observer):
    from .controller import Controller
    from .service import make_server
    from .isolation import WorkerSupervisor
    supervisor = WorkerSupervisor(grace_seconds=.2)
    controller = Controller(database, owner, observer, isolation_callback=supervisor.close)
    def digest_tool(arguments):
        if type(arguments) is not dict or set(arguments) != {'text'} or type(arguments['text']) is not str:
            raise ValueError('bounded text required')
        return {'digest': hashlib.sha256(arguments['text'].encode()).hexdigest(), 'controller_pid': os.getpid()}
    def worker_tool(arguments):
        if arguments != {}:
            raise ValueError('worker takes no agent arguments')
        return {'pid': supervisor.start('demo-worker', [sys.executable, '-c', 'import time; time.sleep(60)'])}
    controller.register_tool('digest', digest_tool)
    controller.register_tool('demo-worker', worker_tool)
    server = make_server(controller)
    connection.send({'endpoint': 'http://127.0.0.1:' + str(server.server_address[1]), 'pid': os.getpid()})
    connection.close()
    try:
        server.serve_forever()
    finally:
        supervisor.close()
        server.server_close()


def demo(directory):
    from .observer import BehaviouralObserver, ObserverClient
    from .alerts import DurableAlertOutbox
    from .model_verification import verify_local_artifacts
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    owner, observer_secret = secrets.token_hex(32), secrets.token_hex(32)
    artifacts = directory/'artifacts'
    artifacts.mkdir()
    (artifacts/'fixture.bin').write_bytes(b'not an LLM; local integrity fixture')
    manifest = {'model': 'local-integrity-fixture', 'revision': 'v1', 'files': {
        'fixture.bin': hashlib.sha256((artifacts/'fixture.bin').read_bytes()).hexdigest()}}
    model = verify_local_artifacts(artifacts, manifest)
    context = multiprocessing.get_context('spawn')
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=_demo_service, args=(child, str(directory/'controller.sqlite3'), owner, observer_secret))
    process.start()
    child.close()
    checks = {}
    service = None
    def denied(operation):
        try:
            operation()
        except PermissionError:
            return True
        return False
    try:
        if not parent.poll(10):
            raise RuntimeError('controller process failed to start')
        service = parent.recv()
        outbox = DurableAlertOutbox(directory/'alerts.sqlite3')
        observer = BehaviouralObserver(directory/'observer.sqlite3', observer_secret, outbox=outbox)
        observed = ObserverClient(service['endpoint'], observer_secret)
        observer.poll(observed)
        scope = {'tenant': 'demo', 'agent': 'learner', 'context': 'read-only'}
        credential = owner_request(service['endpoint'], owner, 'issue_runtime',
            {'scope': scope, 'tools': ['digest', 'demo-worker'], 'models': [model['model_digest']]})['credential']
        runtime = RuntimeClient(service['endpoint'], credential)
        invoke = lambda text: runtime.dispatch(scope, 'digest', model['model_digest'], {'text': text})
        result = invoke('verified ordinary work')
        checks['tool_runs_in_independent_process'] = result['controller_pid'] == service['pid'] != os.getpid()
        checks['wrong_model_denied'] = denied(lambda: runtime.dispatch(scope, 'digest', '0'*64, {}))
        checks['unregistered_tool_denied'] = denied(lambda: runtime.dispatch(scope, 'shell', model['model_digest'], {}))
        observation = observer.poll(observed)
        checks['warning_does_not_stop_authorized_work'] = invoke('continue')['controller_pid'] == service['pid']
        worker_pid = runtime.dispatch(scope, 'demo-worker', model['model_digest'], {})['pid']
        stopped = owner_request(service['endpoint'], owner, 'stop', {'reason': 'owner emergency exercise'})
        checks['owner_stop_revokes_runtime'] = denied(lambda: invoke('after-stop'))
        checks['supervisor_callback_completed'] = stopped.get('isolation_completed') is True
        try:
            os.kill(worker_pid, 0)
            checks['registered_worker_terminated'] = False
        except ProcessLookupError:
            checks['registered_worker_terminated'] = True
        owner_request(service['endpoint'], owner, 'recover', {'reason': 'exercise complete', 'review_ref': 'local-owner-review'})
        checks['old_credential_stays_revoked_after_recovery'] = denied(lambda: invoke('old-token'))
        observer.poll(observed)
        new_credential = owner_request(service['endpoint'], owner, 'issue_runtime',
            {'scope': scope, 'tools': ['digest'], 'models': [model['model_digest']]})['credential']
        recovered = RuntimeClient(service['endpoint'], new_credential)
        checks['reviewed_recovery_with_fresh_credential'] = recovered.dispatch(scope, 'digest', model['model_digest'], {'text': 'recovered'})['controller_pid'] == service['pid']
        report = {'status': 'passed' if all(checks.values()) else 'failed', 'checks': checks,
                  'observer': observation, 'alert_records': len(outbox.status()), 'actual_alerts_sent': 0,
                  'model_verification': model, 'live_llm_calls': 0, 'production_activated': False,
                  'os_identity_separation_verified': False,
                  'limitations': ['Same-UID local process test is not OS isolation.',
                      'No hidden capability absence or hosted model attestation is proved.',
                      'Only registered worker groups and controller-issued credentials were revoked.']}
        (directory/'report.json').write_text(json.dumps(report, indent=2)+'\n')
        return report
    finally:
        parent.close()
        if service is not None and process.is_alive():
            try:
                owner_request(service['endpoint'], owner, 'stop', {'reason': 'demo cleanup'})
            except Exception:
                pass
        if process.is_alive():
            process.terminate()
        process.join(timeout=5)
        if process.is_alive():
            process.kill()
            process.join(timeout=5)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('doctor')
    study = commands.add_parser('demo')
    study.add_argument('--directory', required=True)
    for action in ('stop', 'recover', 'acknowledge_integrity_repair'):
        command = commands.add_parser(action)
        command.add_argument('--endpoint', required=True)
        command.add_argument('--owner-key-file', required=True)
        command.add_argument('--reason', required=True)
        if action != 'stop':
            command.add_argument('--review-ref', required=True)
    args = parser.parse_args(argv)
    if args.command == 'doctor':
        result = {'implemented': ['controller', 'observer', 'owner-stop-recovery', 'alert-outbox', 'local-artifact-verification'],
                  'production_ready': False, 'requires': ['separate OS identities and protected controller state',
                    'exclusive broker possession of protected tool credentials', 'owner-managed alert transports',
                    'deployment-specific adversarial and isolation verification']}
    elif args.command == 'demo':
        result = demo(args.directory)
    else:
        payload = {'reason': args.reason}
        if args.command != 'stop':
            payload['review_ref'] = args.review_ref
        result = owner_request(args.endpoint, _owner_key(args.owner_key_file), args.command, payload)
    print(json.dumps(result, indent=2))
    return int(result.get('status') == 'failed')


if __name__ == '__main__':
    raise SystemExit(main())
