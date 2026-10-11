# Optional Hermes agent integration

Status: adapter and role registry implemented; offline contract/integration tests
pass. No Hermes package installed, live model invoked, or clinical integration
enabled by this stage. Offline tests use a contract double, not the real runtime.

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
