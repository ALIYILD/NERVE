"""Loopback control service. Tool callables are installed by the trusted host.

A separate process prevents runtime object mutation. Separate OS identities,
file permissions and network/tool credentials are deployment requirements;
same-UID tests are not an OS isolation claim. No tool registration endpoint.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

from .client import MAX_BYTES


class BoundedHTTPServer(ThreadingHTTPServer):
    """Limit active connections; owner access still shares listener capacity.

    Production needs a separately administered owner channel/network policy
    for availability under flooding. Request timeouts do not cancel handlers.
    """
    daemon_threads = True

    def __init__(self, address, handler):
        self._slots = threading.BoundedSemaphore(16)
        super().__init__(address, handler)

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()


def make_server(controller, address=('127.0.0.1', 0)):
    if address[0] != '127.0.0.1':
        raise ValueError('controller listens on loopback only')

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never log credentials, prompts, or arguments.

        def setup(self):
            super().setup()
            self.connection.settimeout(3)

        def reply(self, status, value):
            encoded = json.dumps(value, allow_nan=False).encode()
            if len(encoded) > MAX_BYTES:
                status, encoded = 502, b'{"error":"bounded response required"}'
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_POST(self):
            try:
                if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1:
                    raise ValueError('fixed bounded body required')
                size = int(self.headers['Content-Length'])
                if not 0 < size <= MAX_BYTES:
                    raise ValueError('bounded body required')
                raw = self.rfile.read(size)
                if len(raw) != size:
                    raise ValueError('incomplete request')
                value = json.loads(raw)
                if type(value) is not dict:
                    raise ValueError('object required')
                auth = self.headers.get('Authorization', '')
                credential = auth[7:] if auth.startswith('Bearer ') else ''
                if self.path == '/dispatch':
                    if set(value) != {'scope', 'tool', 'model_digest', 'arguments'}:
                        raise ValueError('dispatch fields required')
                    result = controller.dispatch(credential, **value)
                    self.reply(200, {'value': result})
                elif self.path == '/owner':
                    if set(value) != {'action', 'payload', 'nonce', 'timestamp', 'signature'}:
                        raise ValueError('signed owner request required')
                    self.reply(200, controller.owner_request(**value))
                elif self.path == '/heartbeat':
                    if value != {}:
                        raise ValueError('empty heartbeat required')
                    self.reply(200, controller.heartbeat(credential))
                elif self.path == '/report':
                    self.reply(200, controller.report(credential, value))
                elif self.path == '/events':
                    controller._observer_auth(credential)
                    if not set(value) <= {'after', 'limit'}:
                        raise ValueError('invalid event cursor')
                    after, limit = value.get('after', 0), value.get('limit', 8)
                    if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 50:
                        raise ValueError('bounded event cursor required')
                    self.reply(200, controller.events(after=after, limit=limit))
                elif self.path == '/head':
                    if set(value) != {'nonce'}:
                        raise ValueError('observer challenge required')
                    self.reply(200, controller.audit_head(credential, value['nonce']))
                else:
                    self.reply(404, {'error': 'unknown endpoint'})
            except PermissionError:
                self.reply(403, {'error': 'controller denied'})
            except (TypeError, ValueError, KeyError):
                self.reply(400, {'error': 'invalid request'})
            except Exception:
                self.reply(503, {'error': 'controller unavailable'})

    return BoundedHTTPServer(address, Handler)
