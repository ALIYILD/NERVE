#!/usr/bin/env python3
"""Run the independent observer under its own OS identity and private key.

This runner never sends alerts: it queues sanitized incidents for separately
configured delivery. Losing observation does not mint a replacement heartbeat.
"""
import argparse
import json
import os
from pathlib import Path
import stat
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nerve_awim.safety_control.alerts import DurableAlertOutbox
from nerve_awim.safety_control.cli import _owner_key
from nerve_awim.safety_control.observer import BehaviouralObserver, ObserverClient


def interval_value(value):
    number = float(value)
    if not 1 <= number <= 60:
        raise argparse.ArgumentTypeError("interval must be between 1 and 60 seconds")
    return number


def iteration_value(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("iterations must be positive")
    return number


def parser():
    result = argparse.ArgumentParser(description="Independent receipt observer; queues alerts without sending them. Run under an identity the learning worker cannot modify. The controller watchdog must exceed the polling interval.")
    result.add_argument("--endpoint", required=True, help="Controller URL, http://127.0.0.1:PORT")
    result.add_argument("--observer-key-file", type=Path, required=True, help="Private owner-owned regular file, no symlink, 32–4096 bytes; never pass a secret as an argument")
    result.add_argument("--state-directory", type=Path, required=True, help="Private observer cursor and durable alert outbox directory")
    result.add_argument("--interval", type=interval_value, default=5, help="Seconds between polls, 1–60 (default: 5)")
    mode = result.add_mutually_exclusive_group()
    mode.add_argument("--iterations", type=iteration_value, default=1, help="Positive number of polls (default: 1); a failure exits nonzero")
    mode.add_argument("--continuous", action="store_true", help="Poll until interrupted; failures retry after the interval without refreshing the watchdog")
    return result


def run(args, *, client_factory=ObserverClient, observer_factory=BehaviouralObserver,
        sleep=time.sleep, output=None):
    output = output or sys.stdout
    def emit(value):
        print(json.dumps(value, sort_keys=True), file=output, flush=True)
    try:
        if not 1 <= args.interval <= 60 or type(args.iterations) is not int or args.iterations < 1:
            raise ValueError("invalid polling bounds")
        secret = _owner_key(args.observer_key_file)
        client = client_factory(args.endpoint, secret)
        directory = args.state_directory
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise PermissionError("private observer state directory required")
        outbox = DurableAlertOutbox(directory / "alerts.sqlite3")
        observer = observer_factory(directory / "observer.sqlite3", secret, outbox=outbox)
    except Exception:
        emit({"status": "error", "error": "observer setup rejected", "watchdog_refreshed": False})
        return 1
    tick = 0
    try:
        while args.continuous or tick < args.iterations:
            tick += 1
            try:
                result = observer.poll(client)
            except Exception:
                emit({"status": "error", "error": "observation failed", "tick": tick, "watchdog_refreshed": False})
                if not args.continuous:
                    return 1
            else:
                emit({"status": "ok", "tick": tick, "watchdog_refreshed": result["watchdog_refreshed"],
                      "verified_through": result["verified_through"], "incidents": result["incidents"]})
            if args.continuous or tick < args.iterations:
                sleep(args.interval)
    except KeyboardInterrupt:
        emit({"status": "interrupted", "watchdog_refreshed": False})
        return 130
    return 0


def main(argv=None):
    return run(parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
