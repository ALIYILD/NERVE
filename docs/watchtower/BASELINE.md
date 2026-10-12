# Watchtower baseline

Base commit: `23d7900a9e614e313cb70dd8402545960e091de6`. Isolated branch `feat/nerve-watchtower`; production settings unchanged.

Full baseline command: `PYTHONPATH=src /private/tmp/nerve-adaptation-ci-venv/bin/python -m unittest discover -s tests -q`. See [actual output](evidence/baseline.log). The repository is an experimental research system, not a validated clinical deployment.

Discovery covers the tracked source, deployment templates, workflow definitions and operational documentation. No secrets were read, no production services queried, and no live process was stopped. Active production topology, owners, network policy, resource usage and external service health remain UNKNOWN. A checked-in template proves an intended deployment, not an installed service.

Execution families: ARC registered tool dispatcher; repository HTTP host; Agent OS bridge and separate Hermes worker; legacy MCP bridges; parallel research agents; governed memory/learning; shadow/canary/promotion; bounded recursive research; CCE and task adaptation. Scheduled GitHub Actions and user launchd can recreate work independently of a local PID.

Existing shutdown controls are task/engine scoped. The systemd pilot has Restart=on-failure; the Agent OS user launchd schedule runs every 900 seconds. Neither implies external administration separation. DeepSynaps/clinical workflows in this checkout are synthetic contracts; no production endpoint or dependency graph is available.

Telemetry sources include governed-learning SQLite metadata, adaptation events, Agent OS tables and a bounded in-memory v29 trace. Application-owned records are untrusted for automatic critical containment. No latency or availability claim about production is inferred from local tests.
