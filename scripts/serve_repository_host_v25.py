"""Loopback-only pilot; provision trusted OIDC/grants config before starting."""
import argparse
from contextlib import ExitStack
import json
import signal
import tempfile
from pathlib import Path
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server

from nerve_awim.governed_learning_v20 import GovernedLearning, LearningAuthority
from nerve_awim.oidc_v27 import PinnedOIDCVerifier
from nerve_awim.repository_agents_v20 import CONTEXT, REPOSITORY_STRATEGIES, repository_judge
from nerve_awim.repository_host_v25 import HostGrant
from nerve_awim.bound_repository_host_v26 import BoundRepositoryHost
from nerve_awim.store_recovery_v27 import copy_store
from nerve_awim.host_lease import exclusive_host


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *_):
        pass  # Avoid request URLs, bodies and credentials in access logs.


class PilotServer(WSGIServer):
    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(5)
        return connection, address


def build_host(config, database, *, bootstrap=False):
    if type(config) is not dict or set(config) != {'issuer', 'audience', 'jwks', 'grants'}:
        raise ValueError('exact pinned OIDC and grants configuration required')
    verifier = PinnedOIDCVerifier(issuer=config['issuer'], audience=config['audience'], jwks=config['jwks'])
    grants = []
    for entry in config['grants']:
        if type(entry) is not dict or set(entry) != {'subject', 'tenant', 'agent', 'roles'}:
            raise ValueError('invalid grant schema')
        if type(entry['roles']) is not list:
            raise ValueError('grant roles must be a list')
        grants.append(HostGrant(entry['subject'], entry['tenant'], entry['agent'], frozenset(entry['roles'])))
    engine = repository_engine(database)
    return BoundRepositoryHost(engine, verifier=verifier, grants=grants, bootstrap=bootstrap)


def repository_engine(database):
    return GovernedLearning(database, authority=LearningAuthority(), strategies=REPOSITORY_STRATEGIES,
        judge=repository_judge, baseline_routes={CONTEXT: 'ast-inventory'},
        contract_revision='repository-host-v25-tools-v2')


def initialize_database(config, database):
    """Prepare all scopes privately, then publish a new store without overwriting."""
    destination = Path(database).absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError('initialization requires a new database path')
    with tempfile.TemporaryDirectory(prefix='.nerve-init-', dir=destination.parent) as folder:
        staged = Path(folder)/'pilot.db'
        host = build_host(config, staged, bootstrap=True)
        checks = [host.readiness(scope) for scope in host.adapters]
        if not checks or not all(check['ready'] and not check['degraded'] for check in checks):
            raise ValueError('initialization readiness failed')
        copy_store(staged, destination)
    return {'initialized': True, 'ready': True, 'scopes_checked': len(checks)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--database', required=True)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--bootstrap', action='store_true', help='explicitly initialise missing configured scopes')
    parser.add_argument('--check', action='store_true', help='validate configured scopes without listening')
    parser.add_argument('--initialize', action='store_true', help='initialize a new database offline without listening')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('port must be between 1 and 65535')
    if args.check and (args.bootstrap or not Path(args.database).is_file()):
        parser.error('--check requires an existing database and cannot bootstrap')
    if args.initialize and (args.bootstrap or args.check):
        parser.error('--initialize cannot be combined with --bootstrap or --check')
    with ExitStack() as ownership:
        try:
            config = json.loads(Path(args.config).read_text())
            if args.initialize:
                print(json.dumps(initialize_database(config, args.database)))
                return
            database = args.database
            if not args.check:
                database = ownership.enter_context(exclusive_host(database, create=args.bootstrap))
            host = build_host(config, database, bootstrap=args.bootstrap)
            checks = [host.readiness(scope) for scope in host.adapters]
            if not all(check['ready'] for check in checks):
                raise ValueError('startup readiness failed')
        except Exception:
            parser.exit(1, 'Host configuration, database ownership or deployment validation failed.\n')
        if args.check:
            print(json.dumps({'ready': True, 'scopes_checked': len(checks),
                              'degraded_scopes': sum(c['degraded'] for c in checks)}))
            return
        with make_server('127.0.0.1', args.port, host, server_class=PilotServer, handler_class=QuietHandler) as server:
            server.timeout = 1
            print(f'Repository shadow pilot listening on 127.0.0.1:{args.port}', flush=True)
            stopping = False
            def stop(signum, frame):
                nonlocal stopping
                stopping = True
            old_handler = signal.signal(signal.SIGTERM, stop)
            try:
                while not stopping:
                    server.handle_request()  # Response has been sent before learning starts.
                    host.drain(limit=8)
            except KeyboardInterrupt:
                pass
            finally:
                signal.signal(signal.SIGTERM, old_handler)


if __name__ == '__main__':
    main()
