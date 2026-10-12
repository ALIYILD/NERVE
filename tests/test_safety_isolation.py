import os
import sys
import tempfile
import time
from pathlib import Path
import unittest

from nerve_awim.safety_control.isolation import WorkerSupervisor


@unittest.skipUnless(os.name == 'posix', 'POSIX process groups required')
class IsolationTests(unittest.TestCase):
    def test_only_registered_worker_is_terminated_other_scope_continues(self):
        supervisor = WorkerSupervisor(grace_seconds=.2)
        self.addCleanup(supervisor.close)
        command = [sys.executable, '-c', 'import time; time.sleep(60)']
        first = supervisor.start('incident', command)
        other = supervisor.start('independent', command)
        self.assertNotEqual(first, other)
        self.assertFalse(supervisor.stop('unregistered')['isolated'])
        self.assertTrue(supervisor.stop('incident')['isolated'])
        os.kill(other, 0)
        self.assertEqual(supervisor.stop('incident')['status'], 'worker_already_exited')

    def test_duplicate_live_scope_cannot_replace_stop_target(self):
        supervisor = WorkerSupervisor()
        self.addCleanup(supervisor.close)
        command = [sys.executable, '-c', 'import time; time.sleep(60)']
        supervisor.start('worker', command)
        with self.assertRaises(ValueError):
            supervisor.start('worker', command)

    def test_no_shell_or_agent_pid_interface(self):
        supervisor = WorkerSupervisor()
        with self.assertRaises(ValueError):
            supervisor.start('worker', 'echo unsafe; exit 0')
        with self.assertRaises(ValueError):
            WorkerSupervisor(grace_seconds=0)

    def test_late_authorized_launch_cannot_start_after_global_isolation(self):
        supervisor = WorkerSupervisor()
        supervisor.close()
        with self.assertRaises(PermissionError):
            supervisor.start('late', [sys.executable, '-c', 'pass'])

    def test_ignoring_termination_requires_bounded_forced_stop(self):
        supervisor = WorkerSupervisor(grace_seconds=.1)
        self.addCleanup(supervisor.close)
        with tempfile.TemporaryDirectory() as directory:
            ready = Path(directory)/'ready'
            code = ('import signal,sys,time; from pathlib import Path; '
                    'signal.signal(signal.SIGTERM, signal.SIG_IGN); '
                    'Path(sys.argv[1]).write_text("ready"); time.sleep(60)')
            supervisor.start('unresponsive', [sys.executable, '-c', code, str(ready)])
            deadline = time.monotonic()+3
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue(ready.exists(), 'test worker must install its signal handler')
            result = supervisor.stop('unresponsive')
            self.assertTrue(result['forced'])
            self.assertTrue(result['isolated'])


if __name__ == '__main__':
    unittest.main()
