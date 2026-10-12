"""Separate loopback administration portal. No ambient or proxy-header identity."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from .auth import AuthorizationError


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 16
    def __init__(self, *args):
        self.slots = threading.BoundedSemaphore(16)
        super().__init__(*args)
    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise
    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()
    def get_request(self):
        sock, address = super().get_request()
        sock.settimeout(5)
        return sock, address


def create_server(engine, verifier, *, host='127.0.0.1', port=0):
    if host != '127.0.0.1':
        raise ValueError('portal must bind loopback behind independently managed TLS ingress')
    class Handler(BaseHTTPRequestHandler):
        server_version = 'Guardian'
        def log_message(self, *args):
            pass
        def send(self, status, body, content_type='application/json'):
            data = json.dumps(body).encode() if content_type == 'application/json' else body
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(data)
        def principal(self, restart=False):
            auth = self.headers.get_all('Authorization', [])
            if len(auth) != 1 or not auth[0].startswith('Bearer '):
                raise AuthorizationError('owner authentication denied')
            return verifier.verify(auth[0][7:], restart=restart)
        def do_GET(self):
            if self.path in ('/', '/app.js', '/style.css'):
                name, kind = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript'), '/style.css': ('style.css', 'text/css')}[self.path]
                return self.send(200, (Path(__file__).parent / 'static' / name).read_bytes(), kind)
            try:
                principal = self.principal()
                if self.path == '/api/snapshot':
                    return self.send(200, engine.snapshot(principal.tenant))
                if self.path == '/api/audit':
                    return self.send(200, {'records': engine.audit(principal.tenant)})
                self.send(404, {'error': 'not found'})
            except AuthorizationError:
                self.send(401, {'error': 'owner authentication denied'})
            except Exception:
                self.send(503, {'error': 'administration unavailable', 'status': 'UNKNOWN'})
        def do_POST(self):
            principal=None
            def denied():
                if hasattr(engine,'record_denial'):
                    try:engine.record_denial(principal.tenant if principal else None)
                    except Exception:pass
            try:
                if self.path not in ('/api/request-restart', '/api/approve-restart', '/api/keep-stopped'):
                    return self.send(404, {'error': 'not found'})
                principal = self.principal(restart=self.path != '/api/keep-stopped')
                lengths = self.headers.get_all('Content-Length', [])
                if self.headers.get('Transfer-Encoding') or len(lengths) != 1 or self.headers.get('Content-Type') != 'application/json':
                    raise ValueError()
                length = int(lengths[0])
                if not 0 < length <= 4096:
                    raise ValueError()
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict) or not isinstance(body.get('incident_id'), str) or len(body['incident_id']) > 256:
                    raise ValueError()
                if self.path == '/api/request-restart':
                    reference = body.get('cause_reference')
                    if not isinstance(reference, str) or not 1 <= len(reference) <= 256:
                        raise ValueError()
                    result = engine.request_restart(principal, body['incident_id'], reference)
                elif self.path == '/api/approve-restart':
                    request = body.get('request_id')
                    if not isinstance(request, str) or not 1 <= len(request) <= 256:
                        raise ValueError()
                    result = engine.approve_restart(principal, body['incident_id'], request)
                else:
                    result = engine.keep_stopped(principal, body['incident_id'])
                self.send(200, result)
            except (AuthorizationError,PermissionError):
                denied()
                self.send(403, {'error': 'owner authentication denied'})
            except (ValueError, TypeError, KeyError):
                self.send(400, {'error': 'invalid or denied request'})
            except Exception:
                self.send(503, {'error': 'administration unavailable', 'status': 'UNKNOWN'})
    return _Server((host, port), Handler)
