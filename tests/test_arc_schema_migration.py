"""Additive upgrades preserve historical governed rows and legacy manifests."""
import json
import tempfile
import unittest

from nerve_awim.agent_learning_v12 import AgentTask, RegisteredStrategy
from nerve_awim.arc_contracts import SCHEMA
from nerve_awim.arc_execution import ArcRuntime, ToolSpec
from nerve_awim.arc_operations import ArcOperations
from nerve_awim.governed_learning_v20 import GovernedLearning, LearningAuthority


class ArcSchemaMigrationTests(unittest.TestCase):
    def test_historical_governed_rows_and_predecessor_manifest_survive_upgrade_and_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            authority=LearningAuthority()
            operator=authority.issue('tenant','agent','operator')
            reviewer=authority.issue('tenant','agent','operator')
            trainer=authority.issue('tenant','agent','trainer')
            runtime_actor=authority.issue('tenant','agent','runtime')
            engine=GovernedLearning(directory+'/history.sqlite3',authority=authority,
                strategies=[RegisteredStrategy('inspect','inspect',lambda args:{'done':True})],
                judge=lambda task,value:value.get('done') is True,
                contract_revision='migration-v1',baseline_routes={'inspect':'inspect'})
            engine.bootstrap(operator)
            engine.learn_from_task(trainer,AgentTask('historical-task','inspect',{'value':1}))
            original_status=engine.status(operator)
            with engine._db() as con:
                before={table:[tuple(row) for row in con.execute('SELECT * FROM '+table)]
                        for table in ('gl_state','gl_tasks','gl_outcomes','gl_releases','gl_events')}
                # Prior supported manifest schema lacks the optional predecessor
                # link. Keep an actual row so migration tests data preservation.
                con.execute('''CREATE TABLE arc_release_manifests(
                  id TEXT PRIMARY KEY,tenant TEXT,agent TEXT,context TEXT,release TEXT,generation INTEGER,
                  versions TEXT,mode TEXT,previous_mode TEXT,canary_limit INTEGER,used INTEGER,
                  proposer TEXT,status TEXT,review TEXT,created REAL)''')
                versions={'schema':SCHEMA,'prompt':'v1','model':'fixture','policy':'migration-v1','strategy':'inspect'}
                con.execute('INSERT INTO arc_release_manifests VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    ('historical-manifest','tenant','agent','inspect',original_status['active_release'],0,
                     json.dumps(versions),'shadow','off',5,0,operator._nonce,'staged',None,1.))
            runtime=ArcRuntime(engine,tools={'inspect':ToolSpec('inspect',lambda args:True,
                lambda result,args:{'done':result.get('done') is True})})
            operations=ArcOperations(runtime)
            with engine._db() as con:
                for table, rows in before.items():
                    self.assertEqual([tuple(row) for row in con.execute('SELECT * FROM '+table)],rows)
                old=con.execute("SELECT * FROM arc_release_manifests WHERE id='historical-manifest'").fetchone()
                self.assertIsNone(old['previous_manifest'])
                self.assertEqual(old['status'],'staged')
                self.assertEqual(json.loads(old['versions']),versions)
            self.assertEqual(engine.status(operator),original_status)
            operations.promote(reviewer,'historical-manifest',review='migration-reviewed')
            operations.rollback(reviewer,'historical-manifest',review='migration-rollback')
            with engine._db() as con:
                self.assertEqual(con.execute("SELECT status FROM arc_release_manifests WHERE id='historical-manifest'").fetchone()[0],'rolled_back')
                self.assertEqual(con.execute('SELECT mode FROM arc_modes').fetchone()[0],'off')
                self.assertEqual([tuple(row) for row in con.execute('SELECT * FROM gl_tasks')],before['gl_tasks'])
                self.assertEqual([tuple(row) for row in con.execute('SELECT * FROM gl_outcomes')],before['gl_outcomes'])
            self.assertEqual(engine.execute(runtime_actor,AgentTask('post-rollback','inspect',{'value':2}))['value'],{'done':True})
