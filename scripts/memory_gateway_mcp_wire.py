"""Real optional SDK stdio smoke; ephemeral synthetic data, no network traffic."""
import asyncio
import importlib.util
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import tempfile


def returned(result):
    if getattr(result, 'is_error', getattr(result, 'isError', False)):
        raise AssertionError('MCP tool reported error')
    value = getattr(result, 'structured_content', getattr(result, 'structuredContent', None))
    if value is None:
        value = json.loads(' '.join(getattr(block, 'text', '') for block in result.content))
    return value


async def smoke():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
    from nerve_awim.memory_gateway.runtime import load_runtime

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
        public.update(kid='synthetic-mcp', alg='RS256')
        (root/'jwks.json').write_text(json.dumps({'keys': [public]}))
        config = dict(version=1, synthetic_only=True, ledger_path='memory.sqlite', provider='null',
            max_records_per_scope=20,
            oidc=dict(issuer='https://synthetic.invalid', audience='memory', jwks_path='jwks.json'),
            grants=[dict(subject='synthetic-host', tenant_id='research', agent_id='demo', application='demo',
                user='synthetic-user', clinic_id='synthetic-clinic', patient_id='synthetic-patient',
                session_id='stdio-test', roles=['reader', 'writer'])])
        path = root/'runtime.json'
        path.write_text(json.dumps(config))
        runtime = load_runtime(path)
        bound = runtime.sessions['synthetic-host']
        hint = json.dumps(dict(schema='nerve-demo-strategy-v1', task='email-normalization',
                               extract='json-field', normalise='trim-lower'))
        proposed = bound.propose(hint, 'synthetic-host-reviewed-hint')
        reviewer = runtime.gateway.ledger.authority.issue(bound._scope.tenant_id, bound._scope.agent_id,
                                                         permissions=('read', 'approve'))
        runtime.gateway.decide(reviewer, proposed['memory_id'], scope=bound._scope,
                               approve=True, evaluator_id='synthetic-host')
        env = {'PATH': os.environ.get('PATH', ''),
               'PYTHONPATH': str(Path(__file__).resolve().parents[1]/'src'),
               'NERVE_LEARN_DB': str(root/'legacy.sqlite')}
        settings = StdioServerParameters(command=sys.executable,
            args=['-m', 'nerve_awim.learn_mcp', '--memory-config', str(path),
                  '--memory-subject', 'synthetic-host'], env=env)
        async with stdio_client(settings) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = (await session.list_tools()).tools
                required = {'verified_memory_query', 'propose_verified_experience', 'verified_memory_health'}
                names = {tool.name for tool in tools}
                if not required <= names or any(name in names for name in ('approve_memory', 'restore_kv', 'save_kv')):
                    raise AssertionError('unexpected tool boundary')
                for tool in tools:
                    if tool.name in required:
                        schema = getattr(tool, 'input_schema', getattr(tool, 'inputSchema', {}))
                        if set(schema.get('properties', {})) & {'tenant', 'actor', 'scope', 'approve'}:
                            raise AssertionError('identity exposed in tool schema')
                query = returned(await session.call_tool('verified_memory_query', arguments={'query': 'email normalization'}))
                if proposed['memory_id'] not in json.dumps(query):
                    raise AssertionError('approved hint missing')
                pending = returned(await session.call_tool('propose_verified_experience',
                    arguments={'content': 'synthetic unreviewed observation', 'source_id': 'stdio-pending'}))
                if pending.get('status') != 'pending':
                    raise AssertionError('proposal not pending')
                unreviewed = returned(await session.call_tool('verified_memory_query', arguments={'query': 'unreviewed'}))
                if pending['memory_id'] in json.dumps(unreviewed):
                    raise AssertionError('pending proposal became reusable')
                health = returned(await session.call_tool('verified_memory_health', arguments={}))
                if health.get('runtime_restore_enabled') is not False:
                    raise AssertionError('unexpected runtime restoration')
                pipeline = returned(await session.call_tool('run_demo_agent_pipeline', arguments={
                    'task_id': 'stdio-synthetic', 'email_document': '{"email":"  SYNTHETIC@EXAMPLE.ORG  "}'}))
                if (pipeline.get('result') != 'synthetic@example.org'
                        or pipeline.get('verified_memory', {}).get('status') != 'used'
                        or pipeline.get('outcome_memory', {}).get('status') != 'pending'):
                    raise AssertionError('existing demo did not consume approved memory')
                return {'status': 'pass', 'transport': 'official MCP SDK stdio',
                    'mcp_version': importlib.metadata.version('mcp'),
                    'memory_tools_discovered': 3, 'approved_query': 'pass', 'pending_proposal': 'pass',
                    'pending_not_retrievable': 'pass', 'existing_demo_approved_hint': 'pass',
                    'outcome_pending': 'pass', 'kv_restoration': 'disabled', 'synthetic_only': True}


def main():
    if importlib.util.find_spec('mcp') is None:
        print(json.dumps({'status': 'blocked', 'reason': 'official_mcp_sdk_unavailable'}))
        return 2
    try:
        report = asyncio.run(asyncio.wait_for(smoke(), timeout=30))
    except asyncio.TimeoutError:
        print(json.dumps({'status': 'failed', 'reason': 'stdio_timeout'}))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
