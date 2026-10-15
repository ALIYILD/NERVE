# Repository discovery

Repository: ALIYILD/NERVE, local `/Users/aliyildirim/nerve-review`.
Starting HEAD: `c3121d77e1a91535c33047be940d4bacfe06b441`.
Development branch: `codex/robottt-task-adaptation-20261012`.
No applicable AGENTS.md was found in the checkout or its ancestor directories.
Instructions: README.md, CONTRIBUTING.md and `.github/workflows/tests.yml`.
Python source tree uses PYTHONPATH=src, unittest and SQLite; there is no root
package manifest or standalone installed `nerve` executable. The existing CLI
is `python scripts/agentos_bridge.py`.

The initial worktree contained uncommitted ARC files and changes to the shared
governed dispatcher and Agent OS CLI. `starting-worktree.txt` records that state.
These are prerequisites, not newly invented or independently committed modules.
Only narrow additions were made to ARC proposal/dispatch/outcome hooks and CLI
routing. Existing release checks and tool authorization remain authoritative.

| Component | Existing extension point | Adaptation mapping |
|---|---|---|
| Task dispatcher | arc_execution.ArcRuntime, GovernedLearning.execute | Transactional plan, permit and outcome hooks |
| Identity | LearningAuthority / LearningActor | Explicit task capability grants bound to tenant, agent and subject |
| Data store | GovernedLearning._db SQLite | Additive versioned adaptation tables, same transaction boundary |
| Episodes / memory | arc_decisions, arc_evidence, arc_memory | Reference-only events and bounded task state; separate correction lifecycle |
| Verification | ToolSpec.verify / OutcomeRecord | Independent deterministic synthetic tool checks; delayed evidence is unknown |
| Candidate registry | arc_evaluation SQLite candidate tables | Frozen adaptation artifacts and one-use held-out claims |
| Releases | GovernedLearning.activate/rollback, ArcOperations | No new deployment mechanism; research candidates are not executable releases |
| Hermes | hermes_agents.py, hermes_learning.py | Intentionally ineligible: no authenticated task/subject ARC lifecycle binding |
| MCP | learn_mcp.py, learn_v31.py | Existing caller-asserted scope is insufficient; not silently opted in |
| Agent OS | scripts/agentos_bridge.py | Explicit synthetic developer commands; ordinary execution unchanged |
| HTTP repository host | repository_host_v25.py, bound_repository_host_v26.py | No automatic opt-in; requires host task grant mapping |
| Sensor/robot runtime | runtime_v28.py, observed_runtime_v29.py | Ineligible: no physical/device learning activation authorized |
| Metrics | gl_events, ARC operation metrics | Category/mode/backend counts; no task or subject metric labels |
| Research | existing research directory | Optional NumPy external associative memory, no production import |

Baseline results and environment failures are recorded in baseline-results.json.
The restricted runner's existing sandbox-dependent tests failed; the unrestricted
checkpoint passed. The full final run is recorded separately. Python 3.10 was
used for full unit regression; additional CI scripts use isolated Python 3.12.
