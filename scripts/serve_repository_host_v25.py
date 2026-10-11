"""Loopback-only pilot; provision trusted OIDC/grants config before starting."""
import argparse
import json
from pathlib import Path
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server

from nerve_awim.governed_learning_v20 import GovernedLearning, LearningAuthority
from nerve_awim.oidc_v27 import PinnedOIDCVerifier
from nerve_awim.repository_agents_v20 import CONTEXT, REPOSITORY_STRATEGIES, repository_judge
from nerve_awim.repository_host_v25 import HostGrant, RepositoryHost


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
    engine = GovernedLearning(database, authority=LearningAuthority(), strategies=REPOSITORY_STRATEGIES,
        judge=repository_judge, baseline_routes={CONTEXT: 'ast-inventory'},
        contract_revision='repository-host-v25-tools-v1')
    return RepositoryHost(engine, verifier=verifier, grants=grants, bootstrap=bootstrap)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--database', required=True)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--bootstrap', action='store_true', help='explicitly initialise missing configured scopes')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('port must be between 1 and 65535')
    host = build_host(json.loads(Path(args.config).read_text()), args.database, bootstrap=args.bootstrap)
    with make_server('127.0.0.1', args.port, host, server_class=PilotServer, handler_class=QuietHandler) as server:
        server.timeout = 1
        print(f'Repository shadow pilot listening on 127.0.0.1:{args.port}', flush=True)
        try:
            while True:
                server.handle_request()  # Response has been sent before learning starts.
                host.drain(limit=8)
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
