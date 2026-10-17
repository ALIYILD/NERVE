"""Schema bootstrap is durable as a unit, including concurrent/restarted hosts."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.agent_learning_v12 import RegisteredStrategy
from nerve_awim.governed_learning_v20 import GovernedLearning, LearningAuthority
from nerve_awim.arc_execution import ArcRuntime


class AtomicSchemaInitializationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'state.sqlite3'
        with closing(sqlite3.connect(self.path)) as con, con:
            con.execute('CREATE TABLE existing_data(value TEXT)')
            con.execute("INSERT INTO existing_data VALUES ('preserve')")

    def engine(self):
        return GovernedLearning(self.path, authority=LearningAuthority(),
            strategies=[RegisteredStrategy('read', 'read', lambda value: value)],
            judge=lambda *args: True, contract_revision='atomic-schema-test',
            baseline_routes={'read': 'read'})

    def deny_table(self, table):
        original = sqlite3.connect
        def connect(*args, **kwargs):
            con = original(*args, **kwargs)
            con.set_authorizer(lambda operation, name, *_:
                sqlite3.SQLITE_DENY if operation == sqlite3.SQLITE_CREATE_TABLE and name == table
                else sqlite3.SQLITE_OK)
            return con
        return patch('sqlite3.connect', side_effect=connect)

    def tables(self):
        con = sqlite3.connect(self.path)
        try:
            self.assertEqual(con.execute('SELECT value FROM existing_data').fetchall(), [('preserve',)])
            return {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            con.close()

    def test_governed_failure_rolls_back_earlier_ddl_and_preserves_existing_data(self):
        with self.deny_table('gl_tasks'), self.assertRaises(sqlite3.DatabaseError):
            self.engine()
        self.assertNotIn('gl_state', self.tables())
        self.engine()
        self.assertIn('gl_tasks', self.tables())

    def test_arc_failure_rolls_back_earlier_ddl_without_removing_engine_schema(self):
        engine = self.engine()
        before = self.tables()
        with self.deny_table('arc_evidence'), self.assertRaises(sqlite3.DatabaseError):
            ArcRuntime(engine, tools={})
        self.assertEqual(self.tables(), before)
        ArcRuntime(engine, tools={})
        self.assertIn('arc_modes', self.tables())

    def test_concurrent_constructors_and_reopen_preserve_complete_schema(self):
        def initialize(_):
            ArcRuntime(self.engine(), tools={})
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(initialize, range(4)))
        initial = self.tables()
        self.assertTrue({'gl_state', 'gl_tasks', 'gl_events', 'arc_modes',
                         'arc_evidence', 'arc_current', 'arc_decisions', 'arc_memory'} <= initial)
        initialize(None)
        self.assertEqual(self.tables(), initial)


if __name__ == '__main__':
    unittest.main()
