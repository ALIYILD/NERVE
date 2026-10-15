#!/usr/bin/env python3
"""Explicit loopback-only synthetic WSGI host; no automatic deployment."""
import argparse
import json
import socket
from socketserver import ThreadingMixIn
from threading import BoundedSemaphore
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, ServerHandler

from nerve_awim.memory_gateway.runtime import load_runtime


class _DiscardErrors:
    def write(self, _):
        pass

    def flush(self):
        pass


class _QuietHandler(WSGIRequestHandler):
    def handle(self):
        # stdlib WSGIRequestHandler hardcodes multithread=False; advertise
        # the actual execution model to applications running in this host.
        self.raw_requestline = self.rfile.readline(65537)
        if len(self.raw_requestline) > 65536:
            self.requestline = self.request_version = self.command = ''
            self.send_error(414)
            return
        if not self.parse_request():
            return
        handler = ServerHandler(self.rfile, self.wfile, self.get_stderr(),
                                self.get_environ(), multithread=True)
        handler.request_handler = self
        handler.run(self.server.get_app())

    def log_message(self, *_):
        pass

    def get_stderr(self):
        return _DiscardErrors()


class _ThreadedServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True
    block_on_close = False

    def get_request(self):
        sock, address = super().get_request()
        sock.settimeout(self.read_timeout)
        return sock, address

    def process_request(self, request, client_address):
        if not self._workers.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._workers.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._workers.release()

    def handle_error(self, request, client_address):
        # Do not emit request-bearing tracebacks to process logs.
        pass


def _validate_server_options(host, port, read_timeout, max_workers):
    if host not in ('127.0.0.1', '::1'):
        raise ValueError('literal loopback address required')
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError('valid local port required')
    if type(read_timeout) not in (int, float) or not 0 < read_timeout <= 30:
        raise ValueError('socket timeout must be greater than zero and at most 30 seconds')
    if type(max_workers) is not int or not 1 <= max_workers <= 64:
        raise ValueError('one to 64 workers required')


def create_server(service, *, host='127.0.0.1', port=8766, read_timeout=5, max_workers=16):
    _validate_server_options(host, port, read_timeout, max_workers)
    server_class = _ThreadedServer
    if host == '::1':
        class IPv6Server(_ThreadedServer):
            address_family = socket.AF_INET6
        server_class = IPv6Server
    server = server_class((host, port), _QuietHandler, bind_and_activate=False)
    server.read_timeout = read_timeout
    server._workers = BoundedSemaphore(max_workers)
    try:
        server.server_bind()
        server.server_activate()
        server.set_app(service)
    except BaseException:
        server.server_close()
        raise
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--host', choices=('127.0.0.1', '::1'), default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--read-timeout', type=float, default=5)
    parser.add_argument('--max-workers', type=int, default=16)
    parser.add_argument('--check', action='store_true', help='initialise the configured research ledger and report readiness without listening')
    args = parser.parse_args(argv)
    try:
        _validate_server_options(args.host, args.port, args.read_timeout, args.max_workers)
        runtime = load_runtime(args.config)
        if args.check:
            health = runtime.gateway.health()
            print(json.dumps(health, sort_keys=True))
            return 0 if health['status'] == 'ready' else 2
        with create_server(runtime.service, host=args.host, port=args.port,
                           read_timeout=args.read_timeout, max_workers=args.max_workers) as server:
            print(json.dumps({'status': 'listening', 'synthetic_only': True,
                              'host': args.host, 'port': server.server_port}), flush=True)
            server.serve_forever(poll_interval=0.25)
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception:
        print(json.dumps({'status': 'unavailable', 'error': 'memory_runtime_configuration_or_startup_failed'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
