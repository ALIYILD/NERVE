"""Persistent host opt-in for protected runtime dispatch; never local fallback."""
from ..governed_learning_v20 import _id
from .client import RuntimeClient
from .contracts import model_identity


def scope_identity(tenant, agent, context):
    return dict(tenant=_id(tenant), agent=_id(agent), context=_id(context))


def bind(engine, operator, context, client, *, model_digest, tools):
    """Host operator binds one context to server-owned registered tools.

    The learner database stores no credential. Restart requires reattachment.
    Bindings are immutable; do not expose this host API to model-generated code.
    """
    scope = engine._scope(operator, 'operator')
    context = _id(context)
    if not isinstance(client, RuntimeClient):
        raise TypeError('runtime IPC client required')
    model_identity(model_digest)
    strategies = {s for c, s in engine._registry if c == context}
    if not strategies or type(tools) is not dict or set(tools) != strategies:
        raise ValueError('server tool mapping for every registered context strategy required')
    import json
    encoded = json.dumps({k: _id(v) for k, v in tools.items()}, sort_keys=True)
    with engine._db() as con:
        engine._state(con, scope)
        con.execute('''CREATE TABLE IF NOT EXISTS safety_runtime_bindings (
            tenant TEXT, agent TEXT, context TEXT, endpoint TEXT, model_digest TEXT,
            tools TEXT, PRIMARY KEY(tenant,agent,context))''')
        previous = con.execute('SELECT endpoint,model_digest,tools FROM safety_runtime_bindings '
                               'WHERE tenant=? AND agent=? AND context=?', (*scope, context)).fetchone()
        expected = (client.endpoint, model_digest, encoded)
        if previous and tuple(previous) != expected:
            raise PermissionError('protected runtime binding is immutable')
        if previous is None:
            con.execute('INSERT INTO safety_runtime_bindings VALUES(?,?,?,?,?,?)',
                        (*scope, context, *expected))
    attached = getattr(engine, '_safety_clients', {})
    attached[(*scope, context)] = client
    engine._safety_clients = attached


def dispatch_binding(con, engine, actor, context, strategy):
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='safety_runtime_bindings'").fetchone():
        return None
    row = con.execute('SELECT * FROM safety_runtime_bindings WHERE tenant=? AND agent=? AND context=?',
                      (actor.tenant, actor.agent, context)).fetchone()
    if row is None:
        return None
    client = getattr(engine, '_safety_clients', {}).get((actor.tenant, actor.agent, context))
    if not isinstance(client, RuntimeClient) or client.endpoint != row['endpoint']:
        raise PermissionError('persisted protected context requires independent controller client')
    import json
    tools = json.loads(row['tools'])
    if strategy not in tools:
        raise PermissionError('strategy has no protected server tool')
    return client, scope_identity(actor.tenant, actor.agent, context), tools[strategy], row['model_digest']
