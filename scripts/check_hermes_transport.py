"""Real Hermes turns against a deterministic loopback fixture, never a model.

Run in the provisioned isolated Python 3.14 worker with no real credentials.
The Python audit guard is not an OS network sandbox.
"""
import argparse
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import sys
from threading import Thread

from nerve_awim.hermes_agents import HERMES_REVISION, HermesAgentRuntime, load_pinned_factory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--checkout', required=True)
    args = parser.parse_args()
    requests = []
    replies = [json.dumps({'summary': 'Fixture evidence.', 'episodes': ['e1']}),
               json.dumps({'lesson': 'Fixture lesson.', 'episodes': ['e1']}),
               '{"lesson":"first","lesson":"duplicate"}']

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            length = int(self.headers.get('Content-Length', '0'))
            if self.path != '/v1/chat/completions' or not 0 < length <= 262144 or len(requests) >= len(replies):
                self.send_error(400)
                return
            request = json.loads(self.rfile.read(length))
            content = replies[len(requests)]
            requests.append(request)
            response = {'id': 'offline-fixture', 'created': 0, 'model': 'offline-fixture',
                        'object': 'chat.completion',
                        'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': content},
                                     'finish_reason': 'stop'}],
                        'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}}
            if request.get('stream'):
                response['object'] = 'chat.completion.chunk'
                response['choices'][0]['delta'] = response['choices'][0].pop('message')
                body = ('data: ' + json.dumps(response) + '\n\ndata: [DONE]\n\n').encode()
                mime = 'text/event-stream'
            else:
                body, mime = json.dumps(response).encode(), 'application/json'
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    address = server.server_address
    blocked = []

    def audit(event, arguments):
        if event == 'socket.connect' and arguments[1] != address:
            blocked.append(event)
            raise RuntimeError('only fixture connections allowed')

    sys.addaudithook(audit)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    report = {'revision': HERMES_REVISION, 'python': sys.version.split()[0],
              'real_model_calls': 0, 'fixture_turns': 0, 'status': 'blocked'}
    code = 1
    try:
        factory = load_pinned_factory(args.checkout, enabled=True)
        runtime = HermesAgentRuntime(partial(factory, api_key='offline-placeholder'),
            model='offline-fixture', provider='openai',
            base_url=f'http://127.0.0.1:{address[1]}/v1', enabled=True)
        for role, expected in [('research', json.loads(replies[0])), ('skill_builder', json.loads(replies[1]))]:
            result = runtime.execute(role, {'evidence': [{'episode_id': 'e1'}]}, tenant='fixture', agent='probe')
            if result != expected:
                raise AssertionError('fixture response mismatch')
            report['fixture_turns'] += 1
        try:
            runtime.execute('skill_builder', {}, tenant='fixture', agent='probe')
        except ValueError:
            report['duplicate_json_rejected'] = True
        else:
            raise AssertionError('duplicate JSON accepted')
        if len(requests) != 3 or any(request.get('tools') for request in requests):
            raise AssertionError('unexpected request count or tool exposure')
        report['status'] = 'transport_contract_passed'
        code = 0
    except Exception as error:
        report['error_type'] = type(error).__name__
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    report['fixture_requests'] = len(requests)
    report['blocked_python_connections'] = len(blocked)
    print(json.dumps(report, indent=2))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
