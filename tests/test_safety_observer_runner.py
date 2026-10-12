import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest.mock import Mock

from nerve_awim.safety_control import Controller


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "nerve_safety_observer.py"
SPEC = importlib.util.spec_from_file_location("nerve_safety_observer_runner", SCRIPT)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class ObserverRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.secret = "observer-" + "b" * 40
        self.key = self.root / "observer.key"
        self.key.write_text(self.secret)
        self.key.chmod(0o600)
        self.arguments = ["--endpoint", "http://127.0.0.1:9999", "--observer-key-file", str(self.key),
                          "--state-directory", str(self.root / "state")]

    def test_once_uses_real_observer_controller_and_persists_state(self):
        controller = Controller(self.root / "controller.sqlite", "owner-" + "a" * 40, self.secret)
        output = io.StringIO()
        def factory(endpoint, secret):
            self.assertEqual(secret, self.secret)
            return controller
        self.assertEqual(runner.run(runner.parser().parse_args(self.arguments), client_factory=factory, output=output), 0)
        result = json.loads(output.getvalue())
        self.assertTrue(result["watchdog_refreshed"])
        self.assertTrue(controller.status()["observer_fresh"])
        self.assertTrue((self.root / "state" / "alerts.sqlite3").is_file())
        self.assertTrue((self.root / "state" / "observer.sqlite3").is_file())

    def test_failures_sanitized_no_retry_in_once_mode(self):
        observer = Mock()
        observer.poll.side_effect = RuntimeError("secret credential traceback")
        output, sleep = io.StringIO(), Mock()
        self.assertEqual(runner.run(runner.parser().parse_args(self.arguments), client_factory=Mock(),
             observer_factory=Mock(return_value=observer), sleep=sleep, output=output), 1)
        self.assertNotIn("credential", output.getvalue())
        self.assertNotIn(self.secret, output.getvalue())
        self.assertFalse(json.loads(output.getvalue())["watchdog_refreshed"])
        sleep.assert_not_called()

    def test_continuous_failure_retries_after_interval_until_interrupt(self):
        observer = Mock()
        observer.poll.side_effect = RuntimeError("private failure")
        sleep = Mock(side_effect=[None, KeyboardInterrupt()])
        output = io.StringIO()
        args = runner.parser().parse_args(self.arguments + ["--continuous", "--interval", "2"])
        self.assertEqual(runner.run(args, client_factory=Mock(), observer_factory=Mock(return_value=observer),
                                   sleep=sleep, output=output), 130)
        self.assertEqual(observer.poll.call_count, 2)
        self.assertEqual([call.args for call in sleep.call_args_list], [(2.0,), (2.0,)])

    def test_finite_iterations_sleep_only_between_polls(self):
        observer = Mock()
        observer.poll.return_value = {"watchdog_refreshed": True, "verified_through": 1, "incidents": 0}
        sleep = Mock()
        args = runner.parser().parse_args(self.arguments + ["--iterations", "2", "--interval", "1"])
        self.assertEqual(runner.run(args, client_factory=Mock(), observer_factory=Mock(return_value=observer),
                                   sleep=sleep, output=io.StringIO()), 0)
        self.assertEqual(observer.poll.call_count, 2)
        sleep.assert_called_once_with(1.0)

    def test_missing_public_symlink_and_oversized_keys_rejected(self):
        client = Mock()
        self.key.unlink()
        args = runner.parser().parse_args(self.arguments)
        self.assertEqual(runner.run(args, client_factory=client, output=io.StringIO()), 1)
        self.key.write_text(self.secret)
        self.key.chmod(0o644)
        self.assertEqual(runner.run(args, client_factory=client, output=io.StringIO()), 1)
        self.key.chmod(0o600)
        actual = self.root / "actual.key"
        self.key.rename(actual)
        self.key.symlink_to(actual)
        self.assertEqual(runner.run(args, client_factory=client, output=io.StringIO()), 1)
        self.key.unlink()
        self.key.write_text("a" * 4097)
        self.key.chmod(0o600)
        self.assertEqual(runner.run(args, client_factory=client, output=io.StringIO()), 1)
        client.assert_not_called()

    def test_invalid_bounds_and_mutually_exclusive_modes(self):
        for extras in (["--interval", "0"], ["--interval", "61"], ["--interval", "nan"],
                       ["--iterations", "0"], ["--iterations", "-1"],
                       ["--iterations", "2", "--continuous"]):
            with self.subTest(extras=extras), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                runner.parser().parse_args(self.arguments + extras)


if __name__ == "__main__":
    unittest.main()
