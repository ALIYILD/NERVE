"""Schema initialization commits as a unit, including immutable ARC triggers."""
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.agent_learning_v12 import RegisteredStrategy
from nerve_awim.arc_execution import ArcRuntime, ToolSpec
from nerve_awim.governed_learning_v20 import GovernedLearning, LearningAuthority


class SchemaInitializationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'state.sqlite3'

    def engine(self):
        return GovernedLearning(self.path, authority=LearningAuthority(),
            strategies=[RegisteredStrategy('read', 'read', lambda value: value)],
            judge=lambda *_: True, contract_revision='schema-test',
            baseline_routes={'read': 'read'})

    def runtime(self, engine):
        return ArcRuntime(engine, tools={'read': ToolSpec('read', lambda _: True,
                                                        lambda *_: {'done': True})})

    def objects(self):
        with sqlite3.connect(self.path) as con:
            return con.execute('SELECT type,name,sql FROM sqlite_master ORDER BY type,name').fetchall()

    def failure_connection(self):
        connect = sqlite3.connect
        class InterruptedSchema(sqlite3.Connection):
            def executescript(self, sql):
                # Fail after all DDL, before the owning context can commit.
                return super().executescript(sql + '\nSELECT * FROM missing_schema_failure;')
        return lambda *args, **kwargs: connect(*args, factory=InterruptedSchema, **kwargs)

    def test_governed_schema_failure_leaves_no_partial_tables(self):
        with patch('sqlite3.connect', self.failure_connection()):
            with self.assertRaises(sqlite3.OperationalError):
                self.engine()
        self.assertEqual(self.objects(), [])
        self.engine()
        self.assertTrue(any(row[1] == 'gl_state' for row in self.objects()))

    def test_arc_schema_failure_preserves_existing_governed_store(self):
        engine = self.engine()
        before = self.objects()
        with patch('sqlite3.connect', self.failure_connection()):
            with self.assertRaises(sqlite3.OperationalError):
                self.runtime(engine)
        self.assertEqual(self.objects(), before)
        self.runtime(engine)
        self.assertTrue(any(row[1] == 'arc_evidence_immutable' for row in self.objects()))

    def test_successful_schema_reopens_without_changing_definition(self):
        self.runtime(self.engine())
        before = self.objects()
        self.runtime(self.engine())
        self.assertEqual(self.objects(), before)
