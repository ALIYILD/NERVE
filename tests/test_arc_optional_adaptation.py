"""Missing optional code must never erase a persisted task safety contract."""
import sqlite3
from types import SimpleNamespace
import unittest
from nerve_awim.arc_execution import task_hook


class OptionalAdaptationGuardTests(unittest.TestCase):
    def test_absent_module_and_unregistered_tasks_remain_usable(self):
        with sqlite3.connect(':memory:') as con:
            actor=SimpleNamespace(tenant='t',agent='a')
            task_hook(SimpleNamespace(),con,actor,'task','before_plan')
            con.execute('CREATE TABLE adaptation_tasks(id TEXT,tenant TEXT,agent TEXT)')
            con.execute('INSERT INTO adaptation_tasks VALUES(?,?,?)',('other-task','t','a'))
            task_hook(SimpleNamespace(),con,actor,'task','before_plan')

    def test_missing_coordinator_cannot_bypass_persisted_scope(self):
        with sqlite3.connect(':memory:') as con:
            con.execute('CREATE TABLE adaptation_tasks(id TEXT,tenant TEXT,agent TEXT)')
            con.execute('INSERT INTO adaptation_tasks VALUES(?,?,?)',('task','t','a'))
            actor=SimpleNamespace(tenant='t',agent='a')
            for method in ('before_plan','before_execute','record_outcome'):
                with self.subTest(method=method), self.assertRaises(PermissionError):
                    task_hook(SimpleNamespace(),con,actor,'task',method)
            task_hook(SimpleNamespace(),con,SimpleNamespace(tenant='other',agent='a'),'task','before_plan')
