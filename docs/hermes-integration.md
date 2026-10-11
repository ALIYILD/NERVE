# Optional Hermes agent integration

Status: adapter and role registry implemented; offline contract/integration tests
pass. The pinned real runtime was separately provisioned and passed the import
and zero-tool construction probe. No live model was invoked or clinical integration
enabled. Normal unit tests still use a contract double.

## Version contract

Upstream: https://github.com/NousResearch/hermes-agent

Reviewed revision: `c0ef5af5205dbdc25e9e44acd66873b4bb3503c9`

Reviewed source interfaces at that revision: `run_agent.py` (`AIAgent`),
`agent/agent_init.py` (tool and memory configuration), `agent/turn_facade.py`
(`run_conversation`), `agent/conversation_loop.py` (turn result contract).

`load_pinned_factory(checkout, enabled=True)` checks a clean git checkout at the
exact revision, then requires `run_agent` to resolve to that checkout before
importing it. The host must provision dependencies and put the checkout on its
worker's PYTHONPATH. This source pin does not verify dependency supply chains,
ignored files, preloaded modules or external plugins. It is not an OS sandbox.
Do not load an untrusted Hermes installation into the NERVE service process.

## Separate runtime readiness probe

The pinned upstream revision supports Python 3.14 for its runtime; Python 3.12
metadata compatibility is for upgrades and does not provision its dependencies.
NERVE remains on Python 3.12. The real factory loader now rejects an incompatible
interpreter before importing Hermes. Injectable offline contract doubles are
unaffected.

Provision a separate clean checkout and isolated HERMES_HOME/HERMES_RUNTIME_DIR
using upstream `scripts/run-in-hermes-env`. Do not install Hermes dependencies
into NERVE's environment. On containers that cannot preserve archive ownership,
`TAR_OPTIONS=--no-same-owner` allows the upstream bootstrap extraction while
retaining its checksum verification. Upstream PM owns all dependency installation.

From a provisioned worker, with NERVE's src and the Hermes checkout on PYTHONPATH:

```bash
python /path/to/NERVE/scripts/check_hermes_runtime.py --checkout /path/to/hermes-agent
```

Run the probe with an isolated data home and no real provider credentials. It
imports the pinned AIAgent and constructs it with a placeholder key and a dead
loopback endpoint, requests zero tools, then closes the instance. No conversation
is started. A Python audit hook rejects socket connections; this is a probe guard,
not an OS network sandbox or protection from arbitrary subprocesses/plugins.
The JSON report distinguishes import, construction and tool-surface results.
Successful construction does not establish model inference or deployment readiness.

### Measured readiness result (2026-10-11)

The real probe ran on Python 3.14.7: import and construction succeeded, tool count
was zero, and no conversation/model call ran. Eight Python socket connection
attempts during startup were rejected by the audit hook. This confirms startup
can attempt network access even with no conversation; retain host network isolation.
The categorical report is in `docs/hermes-runtime-readiness.json`.

Upstream PM installed the core environment successfully. Optional Chromium failed
to download (byte-range response error); browser tools remain unavailable. A later
activation under a stripped environment tried dependency resolution again and
failed DNS. The successful probe used the already provisioned interpreter returned
by upstream `pm.environments.project_python(Path(checkout))`, without reinstalling
or changing its dependencies. The probe process inherited only PATH, PYTHONPATH,
HERMES_HOME and HERMES_RUNTIME_DIR. This is a local readiness result, not a
reproducibility guarantee for another machine or a passing inference test.

## Core registry

| Role | Function | Implemented execution |
| --- | --- | --- |
| coordinator | Plan/routing advice | Text-only role profile |
| research | Summarize supplied evidence | Source-reference-checked workflow stage |
| memory_curator | Propose memory organization | Text-only profile; ledger owns persistence |
| skill_builder | Propose reusable lesson | Pending ledger proposal with provenance |
| evaluator | Advisory critique | Host independent judge decides test outcomes |
| experiment_runner | Suggest bounded experiments | Text-only profile; existing NERVE loop executes |
| monitor | Explain supplied metrics | Text-only profile; existing NERVE host controls rollback |

These are seven callable role profiles, not seven autonomous deployed services.
Clinical/domain specialist analyzers are not implemented by naming a role.

## Host usage

```python
from nerve_awim.hermes_agents import load_pinned_factory, HermesAgentRuntime

# Only in a provisioned isolated worker with an approved provider and budget:
factory = load_pinned_factory('/opt/hermes-agent', enabled=True)
runtime = HermesAgentRuntime(factory, model=approved_model,
    provider=approved_provider, base_url=approved_endpoint, enabled=True)
```

The default is disabled. Every request creates a fresh session and closes it,
requests zero tools, skips memory/context files and background review, and bounds
iterations/output tokens. Unexpected exposed tools cause rejection before a turn.
Ten sessions per (tenant, agent, role) per runtime object; failures consume quota.
IDs are trusted host routing metadata, not authentication. Host capabilities still
govern ledger reads/proposals; separate worker processes/profiles must enforce
tenant isolation, plugin configuration, network policy and monetary/time limits.
Hermes constructor/import may have side effects and internal API retries. Session
quotas and run_budget_seconds do not constitute a hard dollar/time sandbox.

`hermes_learning.propose_and_evaluate` runs:

1. Validate host memory permissions and study split before any model execution.
2. Read currently approved successful research-memory references.
3. Ask research role for a bounded summary preserving exact evidence IDs.
4. Ask skill-builder role for a lesson using the original evidence and summary.
5. Recheck source evidence and atomically write a pending proposal.
6. Compare baseline and lesson with host-owned independent predictions/judging.

The pipeline summarizes supplied evidence; it does not browse papers itself.
No held-out tasks or expected answers reach either Hermes stage. Runtime text is
untrusted, never executed. Evaluation failures leave a pending proposal. Even a
passing evaluation never approves memory or authorizes deployment. Real-provider
validation, isolation and tool adapters remain follow-up integration work.

All contract tests run in the normal NERVE test suite without credentials or
network access. They cover disabled mode, unexpected tools, failed turns, session
separation, role quotas, forged research references and pending-only publication.
