"""Real separate-process IPC; intentionally same-UID, not OS isolation."""
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import time
import unittest
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from nerve_awim.safety_control.client import RuntimeClient, SafetyUnavailable
from nerve_awim.safety_control.contracts import sign_owner_request
from nerve_awim.safety_control.controller import Controller
from nerve_awim.safety_control.service import make_server
from nerve_awim.safety_control.observer import BehaviouralObserver, ObserverClient

OWNER = 'owner-test-secret-' * 3
OBSERVER = 'observer-test-secret-' * 3
MODEL = 'a' * 64
SCOPE = dict(tenant='tenant', agent='agent', context='work')


def owner(controller, action, payload):
    nonce, stamp = uuid.uuid4().hex, time.time()
    return controller.owner_request(action, payload, nonce, stamp,
                                    sign_owner_request(OWNER, action, payload, nonce, stamp))


def server_process(path, pipe):
    controller = Controller(path, OWNER, OBSERVER, watchdog_seconds=60)
    controller.register_tool('remote-work', lambda payload: {'remote_pid': os.getpid(), 'payload': payload})
    controller.register_tool('uppercase', lambda payload: payload.upper())
    credential = owner(controller, 'issue_runtime', dict(scope=SCOPE, tools=['remote-work', 'uppercase'], models=[MODEL]))['credential']
    controller.heartbeat(OBSERVER)
    server = make_server(controller)
    pipe.send((server.server_address[1], credential))
    pipe.close()
    server.serve_forever(poll_interval=.05)


class ProcessFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        ctx = multiprocessing.get_context('spawn')
        receiver, sender = ctx.Pipe(duplex=False)
        self.process = ctx.Process(target=server_process, args=(str(Path(self.temp.name) / 'controller.sqlite'), sender))
        self.process.start()
        self.addCleanup(self.stop_process)
        sender.close()
        if not receiver.poll(10):
            self.fail('controller process did not start')
        port, credential = receiver.recv()
        receiver.close()
        self.endpoint = f'http://127.0.0.1:{port}'
        self.client = RuntimeClient(self.endpoint, credential)

    def stop_process(self):
        if self.process.is_alive():
            self.process.terminate()
        self.process.join(5)

    def post(self, path, value, credential=''):
        request = Request(self.endpoint + path, data=json.dumps(value).encode(),
                          headers={'Authorization': 'Bearer ' + credential}, method='POST')
        with urlopen(request, timeout=3) as response:
            return json.load(response)

    def owner_post(self, action, payload):
        nonce, timestamp = uuid.uuid4().hex, time.time()
        return self.post('/owner', dict(action=action, payload=payload, nonce=nonce, timestamp=timestamp,
                         signature=sign_owner_request(OWNER, action, payload, nonce, timestamp)))


class SafetyTransportTests(ProcessFixture):
    def test_independent_observer_challenge_and_paginated_signed_events(self):
        for index in range(10):
            self.client.dispatch(SCOPE, 'uppercase', MODEL, str(index))
        observer = BehaviouralObserver(Path(self.temp.name) / 'observer.sqlite', OBSERVER)
        result = observer.poll(ObserverClient(self.endpoint, OBSERVER))
        self.assertGreaterEqual(result['verified_through'], 20)
        self.assertTrue(result['watchdog_refreshed'])
        with self.assertRaises(HTTPError):
            self.post('/head', {'nonce': 'runtime-challenge'}, self.client._credential)

    def test_handler_runs_in_independent_process(self):
        result = self.client.dispatch(SCOPE, 'remote-work', MODEL, {'x': 1})
        self.assertEqual(result['remote_pid'], self.process.pid)
        self.assertNotEqual(result['remote_pid'], os.getpid())
        self.assertEqual(result['payload'], {'x': 1})

    def test_scope_model_tool_and_token_denials(self):
        cases = [(dict(SCOPE, agent='other'), 'remote-work', MODEL),
                 (SCOPE, 'unregistered', MODEL), (SCOPE, 'remote-work', 'b' * 64)]
        for scope, tool, model in cases:
            with self.subTest(scope=scope, tool=tool, model=model), self.assertRaises(SafetyUnavailable):
                self.client.dispatch(scope, tool, model, {})
        with self.assertRaises(SafetyUnavailable):
            RuntimeClient(self.endpoint, 'wrong').dispatch(SCOPE, 'remote-work', MODEL, {})

    def test_owner_stop_and_controller_death_fail_closed(self):
        self.owner_post('stop', {'reason': 'verified-incident'})
        with self.assertRaises(SafetyUnavailable):
            self.client.dispatch(SCOPE, 'remote-work', MODEL, {})
        self.stop_process()
        with self.assertRaises(SafetyUnavailable):
            self.client.dispatch(SCOPE, 'remote-work', MODEL, {})

    def test_runtime_cannot_send_observer_or_owner_requests(self):
        with self.assertRaises(HTTPError) as result:
            self.post('/heartbeat', {}, self.client._credential)
        self.assertEqual(result.exception.code, 403)
        with self.assertRaises(HTTPError):
            self.post('/owner', dict(action='stop', payload={'reason': 'forged'}, nonce='forged',
                                    timestamp=time.time(), signature='forged'), self.client._credential)
        self.assertEqual(self.client.dispatch(SCOPE, 'uppercase', MODEL, 'ok'), 'OK')

    def test_client_rejects_remote_redirect_and_oversized_requests(self):
        with self.assertRaises(ValueError):
            RuntimeClient('http://example.com:80', 'secret')
        with self.assertRaises(ValueError):
            self.client.dispatch(SCOPE, 'remote-work', MODEL, 'x' * 70000)


if __name__ == '__main__':
    unittest.main()
