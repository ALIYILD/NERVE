#!/usr/bin/env python3
"""Print metadata-only preflight. Exit 2 denotes blocked real KV execution."""
import json

from nerve_awim.memory_gateway.galahad_adapter import preflight


def main() -> int:
    report = preflight()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["available"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
