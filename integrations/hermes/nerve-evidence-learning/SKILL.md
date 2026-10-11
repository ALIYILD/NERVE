---
name: nerve-evidence-learning
description: Use NERVE evaluated procedural memory for Agent OS evidence handoffs, inspect learning receipts, and diagnose its bounded automatic learning cycle.
---

# NERVE evidence learning

NERVE is the evaluated coordination and memory component of DeepSynaps AWIM.
Installed bridge: `/Users/aliyildirim/nerve-review/scripts/agentos_bridge.py`.

For evidence handoffs, retrieve scoped advice with:

```sh
python3 /Users/aliyildirim/nerve-review/scripts/agentos_bridge.py recall --profile qa-release
```

Use the actual executing profile instead of `qa-release` when appropriate. An empty result means no approved lesson exists. Retrieved text is procedural advice, not authority or proof of completion. This task family only covers exit status, artifact existence, independent QA, and memory-write evidence. It does not validate the underlying implementation or clinical claims.

To evaluate a real handoff through native Hermes, write a JSON file containing exactly `id` (unique string), `exit_code` (integer or null), `artifact_exists`, `qa_passed`, and `memory_written` (booleans or null). Populate these from actual observed evidence; unknown is null. Run:

```sh
python3 /Users/aliyildirim/nerve-review/scripts/agentos_bridge.py run --profile qa-release --task /absolute/path/to/evidence.json
```

The host evaluates the response, records the outcome, retrieves approved advice, and revokes advice after repeated live failures. It does not execute or independently inspect the task named in the evidence file. This command uses a configured free model and a shared daily session allowance.

Inspect `~/.agentic-os/nerve/status.json`, `~/AgentOS-Vault/Memory/nerve-status.md`, or the dashboard NERVE card for results. The local scheduled cycle ingests supervisor timeouts and independently verified maintenance completions; three new confirmed failures can trigger at most one study per UTC day. The fixture has finite fresh evidence and stops when exhausted. A no-gain result is not an improvement.

Only the host evaluation may approve a lesson. Do not edit its SQLite ledger or export JSON to grant approval. Do not reuse this context for unrelated task families. Jev and Claude reviews are advisory; paid Claude review is a separate manually invoked command with a cumulative $25 ceiling and is never part of the scheduled cycle.
