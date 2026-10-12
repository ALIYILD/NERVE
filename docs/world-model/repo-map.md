# Checkout and integration map

Starting commit: `c3121d77e1a91535c33047be940d4bacfe06b441`.
Plan reference snapshot: `ca1e2d92608654ab5d88c2a5866037656caf4a29`.
Original checkout: `/Users/aliyildirim/nerve-review`, branch
`codex/robottt-task-adaptation-20261012`, with existing ARC/adaptation edits.
Those edits were not imported, modified or reset. Isolated implementation:
`/Users/aliyildirim/nerve-memento3`, branch `codex/memento3-world-model-20261012`.
No existing Memento/world_model implementation was found in the tracked tree.
`CONTRIBUTING.md` requires Python unittest and Node checkpoint tests. CI also
runs the research scripts enumerated in `baseline-evidence.json`. No AGENTS.md
was found in this checkout. There are no production dependency changes.

| Integration owner (code module) | Actual interface and disposition |
|---|---|
| `improvement_loop.py` | `run_improvement_loop`: inspected. Preserve text lesson loop; do not make it execute models. New coordinator keeps its no-automatic-promotion distinction. |
| `governed_learning_v20.py` | `LearningAuthority`, `LearningActor`: reused directly. `GovernedLearning` route schemas are not used to store code manifests. |
| `memory_v18.py` | `TrustedMemoryLedger.propose`: exercised through pending semantic summaries; approval is never inferred from retrieval. |
| `agentos_learning.py` | `AgentOSLearning.observe`, `expected_handoff`: real integration test records host-judged evidence rather than agent rewards. |
| `hermes_learning.py` | Existing `propose_and_evaluate` unchanged; additive `propose_world_rules` uses structured offline runtime fixtures, denies live use. |
| `host_lease.py` | Inspected local flock semantics; not a durable fence. World-model uses SQLite claims/fences instead. |
| `promotion_monitor_v24.py` | Reuse `PromotionMonitor.validate_budget`; simulated release adapter follows generation/fallback semantics with a distinct artifact schema. Actual deployment integration remains pending. |
| `learn_mcp.py` | Additive optional host-bound inspection registration; default `create_server` API behavior unchanged. SDK wire test covers actual tool discovery, allowed lookup and denied lookup. |
| `observed_runtime_v29.py` | `ObservedNerveRuntime.tick` / `sensor_missing`: exercised by normalized simulation adapter; outage remains unavailable. |
| `worldcore_v20.py` | Inspected sensor-aware unavailable/infeasible behavior; no change to control policy. Distributional learning adapter remains pending. |
| `.github/workflows/tests.yml` | Existing checks retained; three offline world-model checks appended. |

Storage: additive `wm_*` SQLite tables, explicit schema migration, no use of a
production DB. Host-owned local files are the trust boundary. Same-process roles
are not claimed to isolate hostile providers or remote callers.

Decisions: finite exact-transition DSL first; no arbitrary Python; no live API
calls; exact typed JSON comparisons; immutable content-addressed artifacts;
conservative no-eligibility outcome where gain is unestablished; real effects
remain unavailable. These are engineering choices, not assertions derived from
an independently inspected copy of the Memento paper.
