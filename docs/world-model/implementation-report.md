# Memento 3 implementation checkpoint — 12 October 2026

**The full 00–19 assignment is not complete.** This branch implements and tests a
bounded offline foundation, not the complete proposed learning system. Loop 00
is complete; loops 01–19 have working portions and remaining requirements listed
individually in [backlog.json](backlog.json). Remaining local implementation work
is not labelled as blocked merely because it is unfinished.

Starting commit: `c3121d77e1a91535c33047be940d4bacfe06b441`.
Branch: `codex/memento3-world-model-20261012`.
Worktree: `/Users/aliyildirim/nerve-memento3`.
No push, PR, merge, production deployment, live-provider call, patient action or
device action was performed. The original checkout's unrelated changes remain
in place. The delivered checkpoint commit is identified in the handoff message.

## Implemented and exercised

- Strict finite JSON policy/rule contracts and explicit additive SQLite migration.
- Scoped ordered prediction reservations followed by immutable outcomes;
  idempotent concurrent delivery and all-or-nothing retrospective import.
- Evidence-linked scripted rules, canonical artifact hashes and tamper checks.
- Finite declarative compilation, a resource-bounded trusted worker process,
  episode replay and independently implemented structural fidelity review.
- Durable final-source reservations, consume-before-evaluate behavior and honest
  stop after a crash loses the final report. Trainer APIs deny final reads.
- Known-state bounded planning, explicit unknowns, policy/stale-observation checks,
  competing hypotheses and simulation-only disagreement probes.
- Durable scripted coordinator checkpoints, leases, fencing, retry limits and
  conservative work reservations; real subprocess restart tests retain state.
- Host-observed `AgentOSLearning.observe` integration, pending memory summaries,
  structured offline Hermes bridge and host-bound MCP inspection through actual
  SDK stdio transport. Existing APIs retain default behavior.
- Pure shadow reporting with unobserved alternatives, atomic simulated release
  bundles and rollback, proposal-only transfer, drift rejection and logical
  evidence tombstones with dependent-model invalidation.
- Existing observed research runtime's outage path returns unavailable; it does
  not fabricate a safe action or deterministic sensor prediction.
- Runnable CLI demo, CI additions and a three-family negative benchmark.

The default configuration remains disabled. Arbitrary Python and live proposal
calls fail closed. Local capabilities are host authorization patterns, not
remote authentication or process isolation from malicious proposers.

## Verification and evidence

[verification.json](verification.json) records exact commands, exit codes,
external evidence paths, log hashes and source hashes. [baseline-evidence.json](baseline-evidence.json)
records the starting checks and their environment limitations.

| Verification | Result |
|---|---|
| Starting Python 3.12 suite outside sandbox | 875 tests passed; 61 optional-dependency skips |
| Integrated suite with CI PyJWT/crypto and MCP dependencies | 903 tests passed, no skips |
| Latest targeted world-model suite | 28 tests passed, including real MCP stdio |
| Existing and appended CI script checks | 48 commands passed |
| Fresh staged-tree export, standalone CLI demo | Passed, eligibility false, simulated rollback observed |
| Git whitespace check | Passed |

The full suite ran before the last strict rule-input validator addition. The
focused suite and fresh-tree demo were rerun after that addition. The CI script
batch ran before the final rollback-demo extension; its final path was then
verified by the fresh-tree demo. No gates or pre-existing tests were weakened.
Test dependencies were installed in a separate virtual environment, not added to
production requirements. The initial sandboxed Python 3.10 checks encountered
OS restrictions and missing MCP; those results are preserved, not called code
regressions or quietly treated as passing.

The fixture demonstration rebuilds a service at a checkpoint; a separate test
resumes the same run in a genuinely new Python process. Crash-after-final
consumption, competing leases, stale fencing, duplicates, wrong goals, invented
evidence, bad executable behavior, transfer authority and rollback persistence
are separately tested. Arbitrary-code probe strings are rejected at the language
boundary; this is not evidence of a verified arbitrary-code OS sandbox.

## Measured outcomes

The fresh demo ends with `inconclusive_independent_gain_not_established`, with
`eligibility=false` and `deployment_authorized=false`. The deliberately damaged
candidate fails replay and fidelity review. Correct finite transitions replay
successfully. Work reservations increase from 3 before restart to 314 at stop;
final sources stay consumed. Simulated regression restores the prior compatible
bundle and increments its generation.

The benchmark contains workflow prerequisites, retry/API stages and data
transformation stages. On **24 final episodes with unseen parameters**, baseline
success is **0/24** and model success is **0/24**, with **24/24 model abstentions**.
There is no observed final gain. Six familiar retained episodes succeed with the
model. These are deterministic synthetic fixture counts, not estimates of
operational efficacy. No confidence interval or clinical validity is claimed.
The replay, rulebook, population and memory-labelled variants currently share
compiled behavior; their causal effects have not been established. This is an
explicit benchmark limitation, not a successful ablation result.

Actual provider use: **0 calls, 0 tokens, 0 provider spend**. External real actions:
**0**. The demo proposer and Hermes test are offline fixtures. Sensor work is
simulation only. No canary or production authorization exists.

## Exact remaining work

1. Complete the proposed typed transition/run/report manifests and provenance,
   revision, latency, dependency and per-category budget accounting contracts.
2. Add a generalizable rule language and genuine code-failure diagnosis;
   integrate bounded multigeneration repair and population selection into the
   coordinator. Hidden-state contradictions currently stop, rather than learn.
3. Separate sealed evaluation storage/process authority, detect semantic task
   clones, freeze/verify the complete policy and dependencies, and compare
   against independently observed incumbent/baseline outcomes. The demo's split
   sources are distinct, but its mechanics and states are intentionally shared.
4. Bind operational planner access to registry eligibility and implement
   reconciled action outboxes if external effects are later enabled.
5. Implement cost-reserving provider adapters before any live smoke test. No key
   is needed for the remaining offline work, and none was read or requested.
6. Add verified OS/container isolation if arbitrary code is needed. macOS hard
   address-space enforcement is not demonstrated by this trusted DSL worker.
7. Replace simulated release exercises with an authenticated host's authorized
   read-only canary path only after independent eligibility is established.
8. Complete causal ablations, continual retention metrics, precise revocation
   dependencies/physical deletion procedures and stochastic sensor evaluation.
9. Finish adversarial crash/timeout/output-limit fault coverage, then rerun all
   acceptance gates on the completed implementation before declaring loops done.

The runnable local mechanism is suitable for continued synthetic engineering
experiments. Live-provider, operational shadow/canary, production and clinical
readiness remain unestablished. See [README.md](README.md) for commands, recovery,
permissions and the exact supported language boundary.
