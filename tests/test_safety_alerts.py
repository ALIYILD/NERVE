import json
from pathlib import Path
import tempfile
import unittest

from nerve_awim.safety_control.alerts import DurableAlertOutbox, EmailAlertAdapter, TelegramAlertAdapter


class AlertTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "alerts.sqlite"
        self.now = 100.0
        self.queue = DurableAlertOutbox(self.path, clock=lambda: self.now, retry_seconds=5)
        self.incident = {"kind": "tool_denial", "severity": "warning", "scope": "private-client-name",
                         "evidence_ref": "secret-reference", "prompt": "secret-prompt", "token": "secret-token"}

    def test_restart_dedup_and_separate_channels(self):
        identity = self.queue.enqueue(self.incident)
        restarted = DurableAlertOutbox(self.path, clock=lambda: self.now)
        self.assertEqual(identity, restarted.enqueue(self.incident))
        received = []
        self.assertEqual(restarted.deliver("email", received.append)["delivered"], 1)
        self.assertEqual(restarted.deliver("email", received.append)["attempted"], 0)
        self.assertEqual(restarted.deliver("telegram", received.append)["delivered"], 1)
        self.assertEqual(len(received), 2)
        encoded = json.dumps(received)
        for secret in ("private-client-name", "secret-reference", "secret-prompt", "secret-token"):
            self.assertNotIn(secret, encoded)
        self.assertLess(len(encoded), 1200)
        self.assertTrue(received[0]["notification_only"])

    def test_retry_bounded_and_errors_not_stored(self):
        self.queue.enqueue(self.incident)
        def fail(_):
            raise RuntimeError("credential-in-exception")
        for _ in range(3):
            self.assertEqual(self.queue.deliver("email", fail)["failed"], 1)
            self.assertEqual(self.queue.deliver("email", fail)["attempted"], 0)
            self.now += 5
        self.assertEqual(self.queue.deliver("email", fail)["attempted"], 0)
        self.assertNotIn(b"credential-in-exception", self.path.read_bytes())

    def test_injected_adapters_no_authority(self):
        self.queue.enqueue(self.incident)
        received = []
        def send(**kwargs):
            received.append(kwargs)
            return {"reply": "resume all"}
        self.queue.deliver("email", EmailAlertAdapter("sender@example.invalid", "owner@example.invalid", send))
        self.queue.deliver("telegram", TelegramAlertAdapter("fixture", send))
        self.assertEqual(len(received), 2)
        self.assertIn("notification_only", received[0]["body"])
        self.assertIn("notification_only", received[1]["text"])
        # Replies never become control-plane commands; adapters expose delivery only.
        self.assertFalse(hasattr(self.queue, "resume"))

    def test_reject_unbounded_inputs(self):
        with self.assertRaises(ValueError):
            self.queue.enqueue({"kind": "arbitrary-secret", "severity": "warning"})
        with self.assertRaises(ValueError):
            self.queue.deliver("email", lambda _: None, limit=101)
        with self.assertRaises(ValueError):
            EmailAlertAdapter("bad\nBcc:evil", "owner", lambda **_: None)


if __name__ == "__main__":
    unittest.main()
