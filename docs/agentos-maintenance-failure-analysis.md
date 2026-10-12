# Agent OS maintenance failure investigation

Observed 12 October 2026, from read-only local board, mission, worker-log, and scheduler inspection. This report contains operational metadata only. It does not claim that a policy benchmark repairs a production timeout.

## Findings at initial inspection

The maintenance board contains 16 runs: 13 completed, two timed out, and one manually reclaimed. Both timeouts exceeded the configured 240-second wall-time limit. The October 5 timeout is still blocking its dependency chain and every subsequent daily mission.

| Run | Role | Recorded duration | Outcome |
| --- | --- | ---: | --- |
| 3, October 3 | QA | 248 seconds | Timed out; watchdog recorded 246 seconds against limit 240 |
| 4, October 3 | QA retry | 188 seconds | Manually reclaimed |
| 5, October 3 | QA retry | 180 seconds | Completed; receipt honestly rejected mission acceptance |
| 16, October 5 | Workflow integrity auditor | 243 seconds | Timed out; watchdog recorded 241 seconds against limit 240 |

Task `t_6f9d7f82` has `max_retries=1`, one consecutive failure, and status `blocked`. Its QA child `t_7f5229d5` and coordinator grandchild `t_f3fe000e` remain `todo`. October 5 has `mission.json` and `routing.json`, but no scheduling, verification, or summary artifact.

The actual producer is `~/AgentOS-Vault/scripts/agent-os-maintenance-mission.py`, not the dashboard repository. At inspection, lines 26–33 created the destination directory and then returned whenever any board task was ready, running, todo, blocked, or review. Empty directories dated October 6–12 are consistent with this gate. The producer's duplicate-work protection is functioning, but a blocked prior mission has no structured recovery/status path. Its gate also omits Hermes's triage state.

The October 12 cron receipt reports `last_status=ok` with a 09:31 BST execution. That demonstrates successful script execution, not completed maintenance: the current mission is absent. A skipped producer must remain visibly distinct from a verified mission.

## What the timeout logs establish

The October 5 worker successfully read its two sources, including a runtime snapshot extending through line 1450. Recorded read durations were 2.6, 2.2, and 1.7 seconds; the clock query took 0.4 seconds. Its remaining log manually recounts schedule entries with inconsistent totals. It ends with an interrupted API call before the required output was written. Heartbeats continue until 08:34:22 UTC; the timeout and circuit breaker fire at 08:34:50 UTC.

This proves wall-time exhaustion during an unfinished model workflow. It does not establish a provider outage as the October 5 cause, nor prove that prompt length alone caused the timeout.

The October 3 shared QA log includes an initial timeout, then explicit provider-unavailable retries during later attempts. Retry delays shown include 17, 33, 66, 64, and 65 seconds. Log entries from different attempts interleave, so provider failures cannot be cleanly attributed to the first timeout from this file alone.

The producer hardcodes `qwen/qwen3.8-27b:free`. Existing NERVE live discovery has already required an available free fallback. Availability must be checked before a new dispatch; current unavailability does not retrospectively explain the October timeouts.

## Smallest practical corrections

1. Preserve the duplicate-work gate but expose a durable blocked-mission receipt with task identities, dependency chain, latest run outcome, and missing artifacts. Inspect before creating a new run directory. Include triage among unresolved states.
2. Produce compact deterministic schedule evidence from the two authorized sources. Count jobs programmatically, keep snapshot timestamps, separate project blockers from infrastructure checks, and distinguish the existing 60-second scheduler tick grace from genuinely overdue work. Do not ask a model to recount the raw JSON.
3. Resolve a currently available free model before dispatch. Keep the wall-time and retry caps. A provider retry must fit the remaining deadline; absent enough time, record incomplete/unknown evidence.
4. Recover only the identified blocked mission under a bounded explicit workflow, preserving its old run and failure evidence. Do not automatically mark old work complete, accept missing output, or bypass dependencies.

These are engineering fixes and recovery controls. Their success needs real output receipts and independent verification; they are not learned-policy gains.

## Independent experiment directions

Fresh tests can target exact enabled-job counts, tick-boundary timestamps, stale execution receipts, dependency gating, timeout/retry budgets, unresolved triage states, missing artifacts, and evidence acceptance. Use synthetic operational metadata matching the observed schemas rather than exposing private job prompts or logs. Baseline and learned arms must receive the same inputs and resources; holdout families must remain separate. Only a measured paired gain warrants a lesson promotion.

## Local evidence references

- `~/.hermes/kanban/boards/agentos-maintenance/kanban.db`: `tasks`, `task_runs`, `task_events`, `task_links` (read-only inspection).
- `~/.hermes/kanban/boards/agentos-maintenance/logs/t_6f9d7f82.log` and `t_829dd4f7.log`.
- `~/AgentOS-Vault/Journal/maintenance-missions/2026-10-05/` and empty later dated directories.
- `~/AgentOS-Vault/scripts/agent-os-maintenance-mission.py`.
- `~/.hermes/profiles/coordinator/cron/jobs.json`: only operational schedule metadata inspected for the report.
- `~/.agentic-os/runtime-utilization.json`: current snapshot timestamp 2026-10-12T09:27:02 UTC at inspection; current schedule and jobs sources both contain 12 enabled jobs.

## Applied recovery

The producer and compact collector described above are now versioned in NERVE and installed locally. The original board was backed up before using the supported API to update the three unresolved task instructions, select the currently available free Nemotron model, and explicitly unblock the timed-out auditor once. Old runs and results were preserved. No timeout or retry limits were increased.

Runs 17, 18 and 19 completed in 100, 75 and 91 seconds respectively. The auditor, QA and coordinator all reached `done`; scheduling, verification and summary artifacts were written. QA returned `accepted: false` because the routing evidence dated from October 5. That is a recovered execution chain, not a verified audit. Its pre-retry snapshot also records the old blocked state; it is not evidence that the recovered board remains blocked.

A separate October 12 mission was then admitted with current evidence, two fresh workers, independent QA and a coordinator. Its four sessions were reserved before dispatch. The learning study remained separate: v3 selection tied 3/3 against 3/3 and produced no approved lesson.

The first October 12 audit exposed a verification gap: scheduling reported `no_paid_model_routes: true` even though the compact source deliberately omitted model and pricing fields. Model QA accepted that assertion by citing the worker report itself. An independent host source review rejected the mission in a separate `host-review.json`; original reports were preserved. The ingest gate now honors that veto. Producer instructions require source-bound checks and an unknown result when evidence is absent. The collector also uses one SQLite read transaction and includes error receipts, invalid inventory and nonlocal delivery in schedule health.

The bounded source recheck corrected the scheduling claim to unknown. A second host source review caught a different unsupported statement: the routing report treated `/api/openrouter/status`'s `ok` flag as evidence of primary model reachability. The dashboard implementation sets that flag to `Boolean(key)` and makes no provider request. The recheck therefore also has a rejected host review, bound to artifact SHA-256 hashes. Future routing and QA instructions explicitly distinguish local credential presence, catalog listing and actual model execution. Completion of the workflow is verified separately from correctness of its reports; neither rejected audit may become a successful learning observation.

Nineteen native sessions were reserved for October 12 in total, including the overnight study, recovery, v3 experiment and both fresh audits. Claude review remains unconnected, with $0 accounted against its $25 ceiling. These changes repair the integration and strengthen evidence checks; measured learned-policy improvement remains unproven.

## Validation

The final NERVE suite passed 735 tests. This includes the real concurrent SQLite snapshot regression, source-health edge cases, producer admission/runtime/model metadata behavior, optional host-review veto, output contract, and isolated v3 behavioral evaluation. Both original study arms and the immutable experiment receipt remain unchanged by these follow-up integration fixes. The final endpoint-semantics prompt clarification is covered by contract tests; a further live audit of that exact prompt has not been run.
