"""Operator-bound HTTP deployments using existing canary/monitor controls.

No remote operator endpoint. A persisted binding follows only its own trial's
baseline, monitored promotion and monitor-owned rollback. Guards are trusted
host callbacks, never supplied by HTTP clients.
"""
from .canary_learning_v23 import CanaryLearning
from .repository_host_v25 import RepositoryHost


class HostDeployments:
    def __init__(self, engine):
        self.engine = engine
        self.controller = CanaryLearning(engine)
        with engine._db() as con:
            con.execute('''CREATE TABLE IF NOT EXISTS gl_http_bindings (
                tenant TEXT, agent TEXT, contract TEXT, canary TEXT, version INTEGER,
                PRIMARY KEY(tenant,agent))''')

    def _binding(self, con, scope):
        row = con.execute('SELECT * FROM gl_http_bindings WHERE tenant=? AND agent=?', scope).fetchone()
        if row is not None and row['contract'] != self.engine.contract:
            raise ValueError('host binding contract changed')
        return row

    def _validate(self, con, scope, state, canary):
        trial = self.controller._row(con, scope, canary)
        if trial['phase'] in ('active', 'ready', 'stopped'):
            expected = (trial['base_release'], trial['base_generation'])
        elif trial['phase'] == 'promoted':
            monitor = self.controller.monitor._row(con, scope, canary)
            if monitor['phase'] == 'active':
                expected = (trial['release'], trial['base_generation'] + 1)
            elif monitor['phase'] == 'rolled_back':
                expected = (trial['base_release'], trial['base_generation'] + 2)
            else:
                raise ValueError('bound monitor was superseded')
        else:
            raise ValueError('trial is not eligible for host routing')
        if (state['active'], state['generation']) != expected:
            raise ValueError('active deployment is outside the approved trial lifecycle')
        return trial

    def bind(self, actor, canary, *, expected_generation, expected_version, reason):
        scope = self.engine._scope(actor, 'operator')
        self.engine._approval_input(expected_generation, reason)
        if type(expected_version) is not int or expected_version < 0:
            raise ValueError('explicit nonnegative binding version required')
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            state = self.engine._state(con, scope)
            old = self._binding(con, scope)
            version = old['version'] if old is not None else 0
            if state['generation'] != expected_generation or version != expected_version:
                raise ValueError('stale deployment/binding approval')
            trial = self._validate(con, scope, state, canary)
            if trial['phase'] not in ('active', 'ready', 'promoted'):
                raise ValueError('cannot newly bind a stopped trial')
            if old is not None and old['canary'] == canary:
                raise ValueError('trial is already bound')
            con.execute('INSERT OR REPLACE INTO gl_http_bindings VALUES(?,?,?,?,?)',
                        (*scope, self.engine.contract, canary, version + 1))
            self.engine._event(con, scope, 'http_trial_bound', {
                'canary': canary, 'version': version + 1,
                'generation': expected_generation, 'review': reason})
        return {'canary': canary, 'version': version + 1}

    def snapshot(self, scope):
        with self.engine._db() as con:
            con.execute('BEGIN')
            self.engine._state(con, scope)
            row = self._binding(con, scope)
            return dict(row) if row is not None else None

    def guard(self, binding):
        def check(con, scope, state):
            current = self._binding(con, scope)
            if binding is None:
                if current is not None:
                    raise ValueError('scope was bound during shadow dispatch')
                return
            if (current is None or current['version'] != binding['version']
                    or current['canary'] != binding['canary']):
                raise ValueError('host binding changed during dispatch')
            self._validate(con, scope, state, current['canary'])
        return check

    def report(self, actor):
        scope = self.engine._scope(actor, 'auditor', 'operator', 'evaluator')
        binding = self.snapshot(scope)
        if binding is None:
            return {'mode': 'shadow', 'binding_version': 0}
        with self.engine._db() as con:
            con.execute('BEGIN')
            state = self.engine._state(con, scope)
            try:
                self.guard(binding)(con, scope, state)
                eligible = True
            except (ValueError, LookupError):
                eligible = False
            has_monitor = con.execute('SELECT 1 FROM gl_promotion_monitors WHERE canary=?',
                                      (binding['canary'],)).fetchone()
        return {'mode': 'controlled', 'binding_version': binding['version'],
                'canary': binding['canary'], 'routing_eligible': eligible,
                'trial': self.controller.report(actor, binding['canary']),
                'monitor': self.controller.monitor.report(actor, binding['canary']) if has_monitor else None}


class BoundRepositoryHost(RepositoryHost):
    def __init__(self, engine, **kwargs):
        self.deployments = HostDeployments(engine)
        super().__init__(engine, **kwargs)

    def _validate_deployment(self, scope, state):
        binding = self.deployments.snapshot(scope)
        if binding is None:
            return super()._validate_deployment(scope, state)
        with self.engine._db() as con:
            con.execute('BEGIN')
            self.deployments.guard(binding)(con, scope, self.engine._state(con, scope))

    def _execute_task(self, scope, task):
        binding = self.deployments.snapshot(scope)
        guard = self.deployments.guard(binding)
        adapter = self.adapters[scope]
        if binding is None:
            result = adapter.execute(task, expected_release=self.bindings[scope],
                                     expected_generation=0, guard=guard)
            return {**result, 'mode': 'shadow', 'learning': 'queued_best_effort', 'cost_usd': None}
        adapter.discard_pending()
        result = self.deployments.controller.execute(adapter.runtime, binding['canary'], task, guard=guard)
        # Never deliver a result after an in-flight rebinding or unrelated release
        # change. Completed observations remain audit evidence, not training rewards.
        with self.engine._db() as con:
            con.execute('BEGIN')
            guard(con, scope, self.engine._state(con, scope))
        return {**result, 'mode': 'controlled', 'learning': 'not_collected_for_training',
                'binding_version': binding['version'], 'cost_usd': None}

    def drain(self, *, limit=32):
        with self._lock:
            result = {}
            for scope, adapter in self.adapters.items():
                if self.deployments.snapshot(scope) is None:
                    result[scope] = adapter.drain(limit=limit, guard=self.deployments.guard(None))
                else:
                    result[scope] = {'discarded_after_binding': adapter.discard_pending()}
            return result

    def _evidence(self, scope):
        report = self.deployments.report(self.auditors[scope])
        if report['mode'] == 'shadow':
            return super()._evidence(scope)
        return {**report, 'shadow': super()._evidence(scope)}
