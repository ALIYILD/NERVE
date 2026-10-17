"""Fail-fast dispatch: no model transport is invoked by these tests."""
import importlib.util
from pathlib import Path
from threading import Barrier, Event, Lock
import unittest

SPEC=importlib.util.spec_from_file_location('overnight_dev_study',Path(__file__).resolve().parents[1]/'scripts/overnight_dev_study.py')
runner=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)

class DispatchTests(unittest.TestCase):
    def test_failure_cancels_before_fifth_item(self):
        barrier=Barrier(4);stop=Event();started=[];mutex=Lock()
        def work(index):
            with mutex:started.append(index)
            barrier.wait(timeout=5)
            if index==0:raise ValueError('injected_transport_failure')
            self.assertTrue(stop.wait(timeout=5))
        with self.assertRaises(ValueError):runner.execute_bounded(range(100),work,stop)
        self.assertEqual(sorted(started),[0,1,2,3])
        self.assertTrue(stop.is_set())
    def test_cancelled_before_admission_makes_no_calls(self):
        stop=Event();stop.set();started=[]
        runner.execute_bounded(range(100),started.append,stop)
        self.assertEqual(started,[])
    def test_success_executes_each_item_once(self):
        stop=Event();started=[];mutex=Lock()
        def work(index):
            with mutex:started.append(index)
        runner.execute_bounded(range(100),work,stop)
        self.assertEqual(sorted(started),list(range(100)))
        self.assertFalse(stop.is_set())
