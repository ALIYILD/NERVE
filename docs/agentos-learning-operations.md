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

The dashboard uses the validated `.next-nerve-v2-check` production build through its launch-agent `NEXT_DIST_DIR` setting. Its original launch configuration is backed up at `~/.agentic-os/nerve/dashboard-launchagent.before.plist`; the first NERVE build configuration is also saved as `dashboard-launchagent.v1.plist`.

## Repository repair and monitored learning

```sh
python3 scripts/agentos_bridge.py repository-tasks
python3 scripts/agentos_bridge.py repository-study
python3 scripts/agentos_bridge.py repository-run --task-id REGISTERED_TASK_ID
```

The default repair profile is `backend-engineer`; `nina-memory-librarian` proposes the lesson. Eleven distinct real NERVE functions receive curated injected faults, split into two training, three selection, three retention, and three final functions. Hidden behavioral tests execute in disposable macOS sandboxed Python processes. Tests, source files, and live services are not changed by generated patches. The benchmark fails closed on unsupported isolation. Known-good reference repairs are checked before any inference.

The evaluator restricts Python syntax and capabilities, denies network and home-file contents, and enforces CPU and wall-clock limits. macOS does not support the requested memory limit on this installation; each execution explicitly reports `memory_limit_enforced: false`. This is not a portable container or a guarantee against memory exhaustion.

The proposal receives training attempts and test summaries only. The host freezes it before selection, randomizes baseline/lesson arm order, and requires the same model, 4096 output-token limit, two-iteration limit, and 90-second outer timeout. Selection ties and regressions stop before final evaluation. Approval requires selection gain, no retention regression, and at least one paired final win with zero losses. These small-sample results do not prove general improvement.

State is durable in `~/.agentic-os/nerve/repository-learning.sqlite3`. Task reservations and outcome events are immutable. Advice retrieval requires the exact profile, model, evaluator revision, and repository scope. A lesson expires after 30 days or is revoked after an observed paired regression or two failures in its latest five monitored uses. Monitoring repeats are deduplicated. Replaying registered tasks is not fresh improvement evidence.

The latest report and generated repairs are saved to `latest-repository-study.json` and `AgentOS-Vault/Journal/nerve/`. The dashboard shows measured scores, active lessons, and rollback counts. Curated fault repairs are separate from fixing naturally occurring production incidents.

For targeted Claude review, use `claude-review --review-target repository-experiments`, `repository-taskbench`, or `repository-runner`. The same cumulative $25 ledger applies. A credential file can be selected using `ANTHROPIC_API_KEY_FILE`; its contents remain local. Review results never grant promotion authority.

See [research and next experiments](agentos-learning-research.md) for the AWIM architecture and evidence limits.
