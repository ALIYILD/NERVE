# Running the local NERVE integration

The Agent OS dashboard at http://localhost:3737 exposes NERVE status through `GET /api/agent-os/nerve`. The repository is installed at `/Users/aliyildirim/nerve-review`; commands below run from that directory.

```sh
python3 scripts/agentos_bridge.py status
python3 scripts/agentos_bridge.py recall --profile qa-release
python3 scripts/agentos_bridge.py cycle
python3 scripts/agentos_bridge.py study --profile qa-release
```

`cycle` collects actual maintenance outcomes. Three newly observed confirmed failures can start one free-model repository repair study per UTC day when fresh task evidence exists. The launch agent `com.aliyildirim.nerve.learning` invokes this every 15 minutes while the user session is active. It does not wake a sleeping Mac. Native sessions are limited to 20 per UTC day, including failed attempts. The finite fresh fixture stops after its available evidence is exhausted. Source-code deployment and broad-task improvement remain separate work.

`study` explicitly starts a bounded experiment, proposes advice with the installed `nina-memory-librarian` Hermes profile, and tests it with `qa-release`. A tie or regression creates no approved memory. The real native runtime uses tools-disabled, isolated sessions and configured available free models. Model identity must remain constant across evaluation arms.

For a live handoff, create an evidence file with an actual unique task ID:

```json
{"id":"actual-task-id","exit_code":0,"artifact_exists":true,"qa_passed":true,"memory_written":false}
```

Then execute `python3 scripts/agentos_bridge.py run --profile qa-release --task /absolute/path/evidence.json`. Use `null` for unobserved facts; never infer QA or memory persistence from the agent saying it succeeded. The bridge judges the supplied facts, not the underlying task artifact itself. Approved advice is retrieved automatically for this run, and repeated failed uses can revoke it.

The installed Hermes skill is `~/.hermes/skills/nerve-evidence-learning/SKILL.md`. Dashboard memory retrieval is explicitly scoped: request `/api/agent-memory/context` with `nerveScope=agentos-evidence-handoff-v1` and `nerveProfile=qa-release`, alongside the endpoint's normal task parameters. It exports only approved, unexpired advice for the exact profile and scope.

The skill source is versioned in `integrations/hermes/nerve-evidence-learning/SKILL.md`. To restore it, copy that directory to `~/.hermes/skills/`; adjust its installation paths when using another machine. Live credentials, SQLite state, vault notes, and launch-agent files remain local and are not published to GitHub.

## Durable evidence

- `~/.agentic-os/nerve/learning.sqlite3`: authoritative receipts, reservations, memories, and outcome utility.
- `~/.agentic-os/nerve/status.json` and `context.json`: dashboard exports.
- `~/.agentic-os/nerve/latest-study.json`: latest measured comparison, with native model receipts.
- `~/AgentOS-Vault/Journal/nerve/`: permanent study receipts and scheduler logs.
- `~/AgentOS-Vault/Memory/nerve-status.md`: readable Obsidian status.

`python3 scripts/agentos_bridge.py sync-gbrain` mirrors the readable status under `nerve-agentos-learning`. The index is informational; it cannot approve memories. `jev-review` requests a semantic review of the latest study, once per day, using the dashboard's configured Jev connection. Its result is advisory and its dollar cost is recorded as unknown.

## Optional Claude review

`claude-review` uses a valid Anthropic API key from `ANTHROPIC_API_KEY` or `~/.agentic-os/anthropic.env`. Keep credentials out of chat and Git. The persistent reviewer ledger enforces this task's $25 ceiling, reserves before calls, reconciles returned usage, and blocks further calls when charges are uncertain. The scheduled cycle never invokes Claude. Account credits alone do not connect the API.

## Scheduler and recovery

```sh
python3 scripts/install_agentos_schedule.py
launchctl load ~/Library/LaunchAgents/com.aliyildirim.nerve.learning.plist
launchctl list com.aliyildirim.nerve.learning
```

Stop automatic cycles with `launchctl unload ~/Library/LaunchAgents/com.aliyildirim.nerve.learning.plist`. Keep the SQLite databases when restarting; deleting state also deletes budgets, deduplication history, and approval provenance. Simultaneous commands are excluded by a host lock; retry after an active study ends.

The dashboard uses the validated `.next-nerve-v3-check` production build through its launch-agent `NEXT_DIST_DIR` setting. Its original launch configuration is backed up at `~/.agentic-os/nerve/dashboard-launchagent.before.plist`; previous NERVE build configurations are also saved as `dashboard-launchagent.v1.plist` and `dashboard-launchagent.v2.plist`.

## Repository repair and monitored learning

```sh
python3 scripts/agentos_bridge.py repository-tasks
python3 scripts/agentos_bridge.py repository-diagnose
python3 scripts/agentos_bridge.py repository-study
python3 scripts/agentos_bridge.py repository-run --task-id REGISTERED_TASK_ID
```

The default repair profile is `backend-engineer`; `nina-memory-librarian` proposes the lesson. Versioned cohorts each contain eleven distinct real NERVE functions with curated injected faults, split into two training, three selection, three retention, and three final functions. The runner selects the first entirely fresh cohort; `--cohort v1`, `--cohort v2`, or `--cohort v3` selects one explicitly. Hidden behavioral tests execute in disposable macOS sandboxed Python processes. Tests, source files, and live services are not changed by generated patches. The benchmark fails closed on unsupported isolation. Known-good reference repairs are checked before any inference.

A study needs room for its worst case of eight native sessions within the existing 20-session UTC daily limit. If insufficient allowance remains, it queues the profile and selected cohort in `~/.agentic-os/nerve/pending-repository-study.json`, without consuming task evidence or making model calls. The scheduled cycle retries the queued request after the UTC day changes, even without three new failures. This requires an active user session; the scheduler does not wake the Mac. The dashboard displays the queued profile, cohort, remaining/required sessions and next UTC-day eligibility separately from the last measured experiment. Pending work cannot appear as a measured improvement. Eligibility is not a promised start time; the active scheduler checks every 15 minutes.

The evaluator restricts Python syntax and capabilities, denies network and home-file contents, and enforces CPU and wall-clock limits. macOS does not support the requested memory limit on this installation; each execution explicitly reports `memory_limit_enforced: false`. This is not a portable container or a guarantee against memory exhaustion.

The proposal receives training attempts and test summaries only. The host freezes it before selection, randomizes baseline/lesson arm order, and requires the same model, 4096 output-token limit, two-iteration limit, and 90-second outer timeout. Selection ties and regressions stop before final evaluation. Approval requires selection gain, no retention regression, and at least one paired final win with zero losses. These small-sample results do not prove general improvement.

State is durable in `~/.agentic-os/nerve/repository-learning.sqlite3`. Task reservations and outcome events are immutable. The database atomically rejects cross-study function-family reuse even when a mutation changes the task hash. Advice retrieval requires the exact profile, model, evaluator revision, and repository scope. For every cohort the revision covers the shared evaluator, cohort source, and extracted task contracts, which are archived before inference. Historical receipts retain their original hashes; older advice does not match the strengthened revision. A lesson expires after 30 days or is revoked after an observed paired regression or two failures in its latest five monitored uses. Monitoring repeats are deduplicated. Replaying registered tasks is not fresh improvement evidence.

The latest report and generated repairs are saved to `latest-repository-study.json` and `AgentOS-Vault/Journal/nerve/`. The dashboard shows measured scores, active lessons, and rollback counts. Curated fault repairs are separate from fixing naturally occurring production incidents.

`repository-diagnose` explains the latest archived receipt without inference, patch execution, or promotion. It checks paired artifacts against phase totals and binds the receipt to the latest ledger study, model, evaluator revision and completed summary. It distinguishes training patch rejection, selection ceiling ties, regressions and missing evidence. The readable diagnosis is also published to Obsidian and `status.json`; `sync-gbrain` mirrors the note. Diagnostic recommendations are engineering follow-ups, not approved learned advice.

For targeted Claude review, use `claude-review --review-target repository-experiments`, `repository-taskbench`, or `repository-runner`. The same cumulative $25 ledger applies. A credential file can be selected using `ANTHROPIC_API_KEY_FILE`; its contents remain local. Review results never grant promotion authority.

See [research and next experiments](agentos-learning-research.md) for the AWIM architecture and evidence limits.

## Maintenance recovery and operational task cohort (12 October)

The versioned daily producer is `integrations/agentos/agent-os-maintenance-mission.py`, installed locally at `~/AgentOS-Vault/scripts/agent-os-maintenance-mission.py`. It resolves the actual provisioned Hermes interpreter, uses the current split Kanban API and Hermes YAML implementation, and selects an available configured free model. Missing or stale catalog metadata is refreshed from the public provider catalog with bounded time and size, verified TLS, zero-price filtering and atomic replacement. A failed refresh blocks new work. All nonterminal tasks prevent duplicate admission; a durable `Journal/maintenance-missions/admission-status.json` distinguishes a blocked producer from completed work. The original producer is backed up under `~/.agentic-os/nerve/maintenance-producer.before-20261012.py`.

`scripts/agentos_maintenance.py` creates a compact read-only operational snapshot. It retains source freshness, exact schedule counts, latest run identities, dependency status and circuit-breaker evidence, without copying job prompts or private log text. Service health and schedule health are separate observations. A snapshot must have a valid collection timestamp before dispatch. Runtime and retry limits remain 240 seconds and one consecutive failure; Hermes's legacy `max_retries` field is a consecutive-failure circuit breaker, not a lifetime run-count budget.

The v3 repair cohort contains eleven new policy functions and injected regression cases adapted from these failure patterns. These are not eleven independently resolved production incidents. Both arms use the same stricter function-only JSON patch contract. The archived [v3 experiment](evidence/agentos-repository-repair-v3.json) recorded both training patches passing, followed by a 3/3 baseline versus 3/3 lesson selection tie. Retention and final tasks were not evaluated, and no lesson was promoted. Comparing training outcomes across different cohorts does not establish that the formatting change caused the difference.

The three explicitly recovered October 5 worker sessions and eight October 12 audit/recheck sessions were reserved in the existing daily native budget before dispatch. Their local reservation receipts and the pre-recovery board backup are retained under `~/.agentic-os/nerve/`. Recovered work is tracked separately from paired learning evidence. See the [incident investigation](agentos-maintenance-failure-analysis.md) for the operational outcome.

An optional `host-review.json` can veto a maintenance mission even when its model QA receipt says accepted. When present it must explicitly accept with nonempty checks and no issues. Missing reviews preserve the existing QA workflow. This additional gate prevents a discovered unsupported claim from entering successful outcome memory; it is not a substitute for checking source evidence. Original worker and QA artifacts remain immutable records of what those agents reported.

## Focused audit regression (12 October follow-up)

`python3 scripts/agentos_audit_regression.py` previews a bounded eight-case evidence test without inference. `--run` uses one `qa-release` native Hermes session under the shared host lock and 20-session daily limit. The host freezes the full prompt, expected labels and revision before inference, records failures, and refuses to repeat an already recorded version. This is a known regression fixture with tools disabled, not a live audit, paired learning comparison or promotion authority.

The [original v1 receipt](evidence/agentos-audit-regression-v1.json) is preserved byte-for-byte. It correctly distinguished credential presence from reachability, missing scheduling price data, catalog listing, explicit host veto and a successful inference receipt. Its raw score is not reliable benchmark evidence: an [independent post-run review](evidence/agentos-audit-regression-v1-review.json), blinded to the output, found one ambiguous gold label. Of the seven defensible cases, six were correct; the remaining error treated missing execution evidence as a contradiction rather than unknown. These are diagnostic observations, not an adjusted improvement score.

The script now has a separately versioned v2 fixture asking directly about provider reachability instead of whether a report independently establishes it. V2 has not been run. All 20 native sessions for October 12 are reserved; no extra model calls or paid reviews were made. The coordinator's installed prompt now honors optional host-review vetoes and reports QA, host and effective verdicts separately. That prompt change is locally tested, not yet validated through another complete live mission.

The [next evaluation design](agentos-next-evaluation.md) proposes a separately scoped evidence-attribution benchmark with citation checks, conflicting receipts and supported controls. Its offline typed oracle, public development controls and freeze/export/grade CLI are implemented; held-out study orchestration is not implemented or queued.

Run `python3 scripts/agentos_audit_bench.py preflight` to validate the offline audit evidence foundation without model calls. See [the implemented foundation and limitations](agentos-next-evaluation.md#implemented-offline-foundation) for its schema, manifest and CLI. Development-control passes are evaluator validation, never model performance or learning gains.
