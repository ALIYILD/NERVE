# Repository discovery and clinical boundaries

This inventory describes checked-in source, not an assertion that any service is deployed. Discovery read source and documentation without accessing production credentials, patient data, or live provider APIs. Baseline test evidence is recorded separately in BASELINE.md.

| Surface | Actual implementation | Visibility and authority limits |
| --- | --- | --- |
| Governed tool execution | `src/nerve_awim/arc_execution.py`, `arc_contracts.py`, `arc_operations.py` | Evidence-bound tool outcomes and local operator controls; not an OS sandbox |
| Repository HTTP host | `repository_host_v25.py`, `bound_repository_host_v26.py`, `scripts/serve_repository_host_v25.py` | Loopback port 8765, pinned OIDC tenant/agent grants; no externally deployed host established |
| Task adaptation | `adaptation.py`, `adaptation_repository.py`, `adaptation_cli.py` | Task-scoped corrections, checkpoints, SQLite receipts and local kill; not external enforcement |
| Governed learning | `governed_learning_v20.py`, `shadow_learning_v21.py`, `canary_learning_v23.py`, `promotion_monitor_v24.py` | SQLite learning/candidate/release history; local capabilities assume trusted host |
| Memory | `memory_v18.py`, `adaptive_memory.py`, `agentos_learning.py`, `hermes_learning.py` | Tenant-scoped SQLite and evaluated procedural lessons; agent-owned storage is not independent evidence |
| Agent OS | `scripts/agentos_bridge.py`, `scripts/agentos_maintenance.py`, `agentos_experiments.py` | Reads external host configuration, launches bounded worker subprocesses; external dashboard/kanban installation not inventoried live |
| Hermes | `hermes_agents.py`, `scripts/agentos_hermes_worker.py` | Pinned external checkout, separate Python 3.14 worker, explicit coordinator/research/memory_curator/skill_builder/evaluator/experiment_runner/monitor roles; this adapter is text-only with tools disabled |
| Other agent paths | `agent_bridge_v13.py`, `parallel_agents_v11.py`, `agents_v30.py`, `collaboration_v31.py`, `learn_mcp.py`, `recovery_mcp_v17.py` | Independent historical/demo/MCP execution surfaces; no universal dispatcher coverage |
| Recursive experiments | `recursive_evolution_v19.py`, `worldcore_recursion_v19.py`, `cue_*` | Bounded research and opt-in cues; not automatic production code evolution |
| Existing telemetry | `telemetry_v29.py`, `observed_runtime_v29.py` | Bounded in-memory event deque; no independent infrastructure trust |
| Identity | `oidc_v27.py`, `identity_v26.py` | Pinned RS256 verifier; existing identity contract alone lacks sufficient fresh MFA evidence for restart |
| Linux service | `deploy/nerve-repository-pilot.service` | Template uses User=nerve, Restart=on-failure, TasksMax=32, MemoryMax=512M and restricted filesystem; deployment unknown |
| macOS scheduling | `scripts/install_agentos_schedule.py` | User launchd job `com.aliyildirim.nerve.learning`, 900-second interval; stopping one PID does not disable recreation |
| External CI | `.github/workflows/recursive-research.yml` | Scheduled every six hours; bounded data-only experiment, read-only contents/actions permissions; not stopped by local process control |
| Provider boundary | `agentos_bridge.py`, `agentos_hermes_worker.py`, `agentos_claude.py`, `arc_provider.py` | OpenRouter and Anthropic integration code; credential contents deliberately not read, active destinations and permissions unknown |

## Collection design

`SQLiteMetadataSource` polls only explicitly configured local files using SQLite `mode=ro`, `query_only`, disabled trusted schema and a bounded progress deadline. Only fixed SQL count queries are allowed. Governed tables filter `tenant`; adaptation child tables join their task's tenant. Views are rejected. Raw records, source code, prompts, credentials, patient fields and exception messages are never emitted. AgentOS tables lacking a tenant column are deliberately not collected by this generic adapter; dedicated tenant-safe adapters are still a coverage gap.

`BoundedCollector` uses a capped queue, one independent daemon worker and capped output retention. Submission does not wait. Drops and inactive workers report UNKNOWN. Retention is an in-memory bound, not durable incident retention. Independently administered storage must receive snapshots with its own access policy and retention. Configure administrative tenant/source identifiers without patient names or secrets. NERVE execution imports none of this package and remains independent of collector health.

Snapshots identify `source_type=application_untrusted`. `status=OK` means configured metadata was read; it does not mean system safety. Every snapshot explicitly retains gaps for unverified application activity freshness and missing independent infrastructure. `BehaviourAnalysis` evaluates bounded empirical activity-rate deltas, stale/malformed/replayed observations and decreasing counts. It never returns CRITICAL or authorizes containment. NORMAL applies only to the configured metadata baseline; coverage stays UNKNOWN. Baseline poisoning, application tampering and unobserved workloads require independent controls.

## Clinical dependency analysis

`arc_workflows.py` implements `SyntheticClinicalBoundary`; `arc_operations.py` rejects clinical activation without external domain review. The checkout contains no live DeepSynaps Clinical OS referral endpoint contract, no clinical service deployment topology and no patient-data integration verified here. CCE eligibility excludes clinical/high-risk tasks. These facts must not be translated into a clinical safety guarantee.

A production containment inventory must exclude shared clinical dependencies until owners map queues, databases, human-facing care pathways and downstream service dependencies, define safe degradation and approve exact targets. Never stop a shared database, network, identity provider or host merely because a NERVE-related process appears there. Rooted scope selection and service-specific enforcement are mandatory. A local safety controller cannot claim universal shutdown across Clinical OS, cloud workers, externally scheduled research or remote providers.

## Unknowns requiring independent provisioning

Active service/unit/process inventory; container/cloud deployments; real network destinations and egress enforcement; production IAM grants; workload versus owner administrative identities; deployment signing/provenance; shared clinical dependencies; externally retained audit storage; test Telegram/email credentials; external Guardian heartbeat monitoring; OS-level protection preventing agents from modifying safety code/configuration; provider credential revocation capability. No live shutdown test or production setting change was performed.
