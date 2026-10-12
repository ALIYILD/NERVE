"""Authorization regressions for consolidation of repeated adaptation reads."""
import tempfile
import unittest
from nerve_awim.adaptation import task_hook
from nerve_awim.adaptation_replay import build,start

class AdaptationReadTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.c=build(self.tmp.name+'/state.db',now=lambda:100.)
        start(self.c);self.a=self.c['adaptation'];self.actor=self.c['actor']
    def test_grant_revocation_is_observed_without_cached_authorization(self):
        with self.c['engine']._db() as con:
            self.a._row(con,self.actor,'task')
            con.execute('DELETE FROM adaptation_grants WHERE task=? AND principal=?',('task',self.actor._nonce))
            with self.assertRaises(PermissionError):self.a._row(con,self.actor,'task')
    def test_scope_predicate_still_required_even_with_a_grant(self):
        other=self.c['authority'].issue('other-tenant','adaptation-agent','runtime')
        with self.c['engine']._db() as con:
            con.execute('INSERT INTO adaptation_grants VALUES(?,?)',('task',other._nonce))
            with self.assertRaises(PermissionError):self.a._row(con,other,'task')
    def test_revoked_actor_denied_before_database_capability_lookup(self):
        self.c['authority'].revoke(self.actor)
        with self.c['engine']._db() as con:
            with self.assertRaises(PermissionError):self.a._row(con,self.actor,'task')
    def test_persisted_task_hook_requires_coordinator_after_omission(self):
        self.c['runtime'].adaptation=None
        with self.c['engine']._db() as con:
            with self.assertRaisesRegex(PermissionError,'persisted adaptation'):
                task_hook(self.c['runtime'],con,self.actor,'task','before_execute','missing')
    def test_attached_hook_reads_current_kill_switch(self):
        self.a.kill_switch(self.c['operator'],reason='test-reviewed-stop')
        with self.c['engine']._db() as con:
            with self.assertRaises(RuntimeError):
                task_hook(self.c['runtime'],con,self.actor,'task','before_plan',parent=None,tool='note',evidence_refs=[])


def development_profile():
    """Interleave exact before/after read functions on generated development tasks.

    This intentionally does not load any adaptation selection or sealed suite.
    Reads the trusted baseline commit to avoid maintaining a second implementation.
    """
    import json
    import random
    import statistics
    import subprocess
    import sys
    import time
    import types
    import nerve_awim.adaptation as current
    from nerve_awim.adaptation_replay import episode
    baseline='64b6073'
    previous=types.ModuleType('nerve_awim._adaptation_profile_before')
    sys.modules[previous.__name__]=previous
    exec(subprocess.check_output(['git','show',baseline+':src/nerve_awim/adaptation.py'],text=True),previous.__dict__)
    new_row=current.AdaptationCoordinator._row
    new_hook=current.task_hook
    elapsed={'before':[],'after':[]}
    reads={'before':[],'after':[]}
    query_counts={}
    rng=random.Random(4721)
    try:
        for repetition in range(12):
            order=['before','after'];rng.shuffle(order)
            for arm in order:
                current.AdaptationCoordinator._row=previous.AdaptationCoordinator._row if arm=='before' else new_row
                current.task_hook=previous.task_hook if arm=='before' else new_hook
                with tempfile.TemporaryDirectory() as directory:
                    c=build(directory+'/micro.db',now=lambda:100.);start(c)
                    with c['engine']._db() as con:
                        statements=[];con.set_trace_callback(statements.append)
                        c['adaptation']._row(con,c['actor'],'task')
                        query_counts[arm]=len(statements)
                        con.set_trace_callback(None)
                        began=time.perf_counter()
                        for _ in range(2000):c['adaptation']._row(con,c['actor'],'task')
                        reads[arm].append(time.perf_counter()-began)
                    began=time.perf_counter()
                    for index in range(12):
                        episode(directory+'/'+str(index)+'.db',{'id':'development-'+str(index),'family':'heading','heading':'verified-development','template':'development-only'})
                    elapsed[arm].append(time.perf_counter()-began)
    finally:
        current.AdaptationCoordinator._row=new_row
        current.task_hook=new_hook
        del sys.modules[previous.__name__]
    return {'scope':'interleaved development diagnostic; no frozen holdout','baseline':baseline,
            'seed':4721,'rounds':12,'episodes_per_round':12,'episode_seconds':elapsed,
            'episode_median':{k:statistics.median(v) for k,v in elapsed.items()},
            'authorized_read_seconds':reads,'authorized_read_median':{k:statistics.median(v) for k,v in reads.items()},
            'sql_statements_per_authorized_read':query_counts}

if __name__=='__main__':
    import json
    import sys
    if sys.argv[1:]==['--profile']:
        print(json.dumps(development_profile(),indent=2))
    else:
        unittest.main()
