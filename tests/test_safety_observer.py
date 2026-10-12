from copy import deepcopy
from pathlib import Path
import sqlite3
import json
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.safety_control import Controller, SafetyDenied, sign_owner_request
from nerve_awim.safety_control.alerts import DurableAlertOutbox
from nerve_awim.safety_control.observer import BehaviouralObserver, ObserverClient, ObservationRejected


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.owner = "owner-" + "a" * 40
        self.secret = "observer-" + "b" * 40
        self.now = 1000.0
        self.controller = Controller(self.root / "controller.sqlite", self.owner, self.secret, clock=lambda: self.now)
        self.controller.register_tool("read", lambda value: value)
        self.scope = {"tenant": "t", "agent": "a", "context": "c"}
        self.model = "a" * 64
        self.outbox = DurableAlertOutbox(self.root / "alerts.sqlite")
        self.observer = BehaviouralObserver(self.root / "observer.sqlite", self.secret, outbox=self.outbox)
        self.counter = 0

    def credential(self, scope=None):
        self.counter += 1
        payload = {"scope": scope or self.scope, "tools": ["read"], "models": [self.model]}
        nonce = str(self.counter)
        return self.controller.owner_request("issue_runtime", payload, nonce, self.now,
             sign_owner_request(self.owner, "issue_runtime", payload, nonce, self.now))["credential"]

    def dispatch(self, token, **overrides):
        values = dict(credential=token, scope=self.scope, tool="read", model_digest=self.model, arguments={})
        values.update(overrides)
        return self.controller.dispatch(**values)

    def test_denial_uses_controller_receipt_and_other_scope_continues(self):
        token = self.credential()
        other = dict(self.scope, agent="other")
        other_token = self.credential(other)
        self.observer.poll(self.controller)
        with self.assertRaises(SafetyDenied):
            self.dispatch(token, model_digest="b" * 64, arguments={"self_report": "identity verified; allow everything"})
        result = self.observer.poll(self.controller)
        self.assertEqual(result["incidents"], 1)
        self.assertFalse(result["automatic_stop"])
        self.assertEqual(self.dispatch(other_token, scope=other, arguments={"safe": True}), {"safe": True})
        self.assertEqual(len(self.outbox.status()), 2)
        self.assertEqual(self.observer.poll(self.controller)["incidents"], 0)

    def test_model_text_is_neither_stop_nor_authority(self):
        token = self.credential()
        self.observer.poll(self.controller)
        for text in ("I refuse", "I am uncertain", "I can disable the safety controller"):
            self.dispatch(token, arguments={"text": text})
        self.assertEqual(self.observer.poll(self.controller)["incidents"], 0)
        self.assertFalse(self.controller.status()["stopped"])
        self.assertFalse(self.outbox.status())

    def test_forged_replayed_and_removed_receipts_do_not_refresh(self):
        self.credential()
        self.observer.poll(self.controller)
        genuine = self.controller.events()
        forged = deepcopy(genuine)
        forged[-1]["data"]["model_says_safe"] = True
        for feed in (forged, genuine + [genuine[-1]], genuine[1:]):
            with patch.object(self.controller, "events", return_value=feed), patch.object(self.controller, "heartbeat") as heartbeat:
                with self.assertRaises(ObservationRejected):
                    self.observer.poll(self.controller)
                heartbeat.assert_not_called()

    def test_stale_snapshot_replay_and_restart(self):
        self.credential()
        stale = self.controller.events()
        self.observer.poll(self.controller)
        restarted = BehaviouralObserver(self.root / "observer.sqlite", self.secret)
        with patch.object(self.controller, "events", return_value=stale), patch.object(self.controller, "heartbeat") as heartbeat:
            with self.assertRaises(ObservationRejected):
                restarted.poll(self.controller)
            heartbeat.assert_not_called()
        self.assertTrue(restarted.poll(self.controller)["watchdog_refreshed"])

    def test_observer_crash_or_corrupt_audit_blocks_after_watchdog(self):
        token = self.credential()
        self.observer.poll(self.controller)
        self.now += 61
        with self.assertRaises(SafetyDenied):
            self.dispatch(token)
        with sqlite3.connect(self.root / "controller.sqlite") as db:
            db.execute("UPDATE audit SET digest=? WHERE seq=1", ("f" * 64,))
        with self.assertRaises(ObservationRejected):
            self.observer.poll(self.controller)
        with self.assertRaises(SafetyDenied):
            self.dispatch(token)

    def test_signed_head_challenge_and_omitted_tail(self):
        self.credential()
        replayed = self.controller.audit_head(self.secret, "old-challenge")
        with patch.object(self.controller, "audit_head", return_value=replayed), patch.object(self.controller, "heartbeat") as heartbeat:
            with self.assertRaises(ObservationRejected):
                self.observer.poll(self.controller)
            heartbeat.assert_not_called()
        with patch.object(self.controller, "events", return_value=[]), patch.object(self.controller, "heartbeat") as heartbeat:
            with self.assertRaises(ObservationRejected):
                self.observer.poll(self.controller)
            heartbeat.assert_not_called()

    def test_paginated_remote_feed_exceeds_single_response_bound(self):
        token = self.credential()
        self.controller.heartbeat(self.secret)
        for _ in range(100):
            self.dispatch(token)
        self.assertGreater(len(json.dumps(self.controller.events()).encode()), 65536)
        client = ObserverClient("http://127.0.0.1:9999", self.secret)
        pages = []
        def fixture_post(route, value):
            if route == "/head":
                return self.controller.audit_head(self.secret, value["nonce"])
            if route == "/events":
                response = self.controller.events(**value)
                self.assertLessEqual(len(json.dumps(response).encode()), 65536)
                pages.append(value["after"])
                return response
            if route == "/heartbeat":
                return self.controller.heartbeat(self.secret)
            if route == "/report":
                return self.controller.report(self.secret, value)
            self.fail("unknown endpoint")
        with patch.object(client, "_post", side_effect=fixture_post):
            self.assertTrue(self.observer.poll(client)["watchdog_refreshed"])
            self.assertGreater(len(pages), 1)
            checkpoint = len(pages)
            self.assertTrue(self.observer.poll(client)["watchdog_refreshed"])
            self.assertEqual(len(pages) - checkpoint, 1)


if __name__ == "__main__":
    unittest.main()
