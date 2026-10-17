# Morning report — 17 October 2026 overnight run

**Outcome: the night built a lot of CPU work and admitted no learning study.** Inference was never admitted after the first B01b dev study. The registered preflight failed on cold-start latency, two coordinators deadlocked on `preflight_ok`, and the Codex usage limit stopped every window at about 02:30 London (01:30 UTC) until 22 October. No pod could be stopped after that. A recovery pod sat idle for 5.7 hours until the morning close.

This close was done by one writer: Claude Code in a terminal on the laptop. It made no model calls, signed nothing, ran no test tiers and made no inference requests.

## Pods and spend

All six pods were checked in the RunPod console at 07:08 UTC (08:08 London), and all six show EXITED. Claude Code stopped lvojhtouu5gede in the operator's signed-in console session on the operator's instruction. The figures below are **console-verified by the operator, not verified through the API**. No `RUNPOD_API_KEY` exists on the laptop.

| Pod | Role | Billable intervals (UTC) | Est. compute | Final |
|---|---|---|---|---|
| 5xndo7i7s5r9zn | A | 16 Oct 23:45:14–23:59:51; 17 Oct 00:00:25–00:07:00 (00:59 restart rejected) | $0.2085 | EXITED |
| lvojhtouu5gede | B, then recovery | 00:59:35–01:05:01; **01:27:11–07:08:14 (idle)** | $0.0535 + **$3.3537** | EXITED (stopped 07:08:14) |
| ki9m7vdg9qsea6 | — | none tonight | $0 | EXITED |
| b7qj6qyx9ij6gg | — | none tonight | $0 | EXITED |
| 97vr620wnmtuga | — | none tonight | $0 | EXITED |
| lg0svvuenxvbno | PerfFlux demo, not NERVE | none tonight | $0 | EXITED |

How the spend reconciles:
- The ledger shows 117 model calls and $0.2619 of compute up to 01:24 UTC.
- The recovery interval adds $3.3537 at $0.59/h and has no recorded calls.
- **Total estimated compute is $3.6156 against the $12 cap.**
- Storage is excluded. Each stopped pod accrues idle disk at about $0.003/h.
- This is not a provider invoice.

The source is `~/nerve-orchestration/spend.json` (`morning_close`), snapshotted in [orchestration/morning-close-20261017/](../../orchestration/morning-close-20261017/), along with a console screenshot.

## D1–D10

Status is judged against the definitions in [overnight-orchestration-plan-20261017.md](overnight-orchestration-plan-20261017.md) and the D9/D10 rows of W0's continuation status.

| | Deliverable | Status | Evidence |
|---|---|---|---|
| D1 | Studies ingested to v2, ≥3 autonomous proposals per family, rejection memory | **Not achieved** | W2 imported 100 historical B episodes and generated two failure-cluster proposals from them. That is historical reuse, not fresh iterations. Family A has no trial, and no family reached three proposals. (`orchestration/morning-close-20261017/w2-status.md`) |
| D2 | ≥1 dev keep per family beating incumbent and controls | **Not achieved** | B01b scored 35 wins, 0 losses and 65 ties with both controls passing: a verified dev keep, but limited to two agreement strata in Family B. Family A has no keep. ([overnight-closeout-independent-20261017.md](overnight-closeout-independent-20261017.md)) |
| D3 | ≥1 sealed promote_proposal queued for a human | **Not achieved** | No eligible broad candidate and no fresh sealed study. The queued gate payload is not a candidate promotion. |
| D4 | Qualifying fresh-seed gate v3.2 | Partial | The doc 129 grid fails its original harmful-zero criterion. Under the bounded-rate reformulation (doc 130, commit `49bbe7b`), m=14 with seed 2026102501 ran 100,000 streams per profile. Harmful accepts were 3 / 1 / 0, with upper bounds 0.00775% / 0.00474% / 0.00300%, all within the 0.05% limit. The payload is queued **unsigned** and is now held pending (see the signing queue section). |
| D5 | Registered scientific drift and restart | **Not achieved** | The canonical scientific paired stream never ran because same-task retained A/B outcomes are missing. The synthetic 1,200-item drift and SIGKILL restart replay is separate evidence and does not satisfy D5. (`w3-status.md`) |
| D6 | Both sandbox adaptations | Achieved (synthetic contract scope only) | The PerfFlux and Clinical OS sandbox bundles replay independently (commits `942ebbe`, `3ffb8c2` on `overnight/w3-adapt-sdk`). No real workload reward and no clinician reward. |
| D7 | Complete SDK, demos and contracts | Partial | Five interfaces, a CLI, three demos, atomic ingestion and v2 contracts are built. The integrated fast-tier and CI result is unresolved, and signed evaluation is delegated externally. |
| D8 | Independent verification, shutdown and spend | Partial | Protected hashes match 80/80 on every branch head. All six pods are EXITED, verified in the console this morning. Spend is estimated, not invoiced. There is no verified merge and no final L7 replay. |
| D9 | Advisor calibration | Not achieved | No prospective cycle verdicts exist to calibrate against. |
| D10 | Faithfulness | Partial | A trace-consistency monitor and fixtures are built (`75b7d5d`). There is no live experiment coverage. |

## CPU deliverables that landed

All of these are on worker branches and none are merged.

| Deliverable | Commit(s) | Branch |
|---|---|---|
| Gate v3.2 coverage grid (doc 129), reverified | `b97aabf` (parent), `46b0f2d` | `overnight/w1-gate` |
| Bounded harmful-rate qualification and unsigned v3.2 payload | `49bbe7b` | `overnight/w0-orchestrator` |
| Faithfulness / trace-consistency monitor | `75b7d5d` | `overnight/w2-autoresearch`, `overnight/resume-admission-guard` |
| Bank v5 and v5 dev-discrimination study (built before launch, 16 Oct evening) | `7cc51c0`, `450b84c` | base |
| Admission guard: ledger-bound preflight and focused evidence | `f59fe32`, `e69e136` | `overnight/resume-admission-guard` |
| Atomic ARC/governed schema initialisation. ARC suite time fell from 28.7 s / 25.5 s to 16.7 s / 16.0 s, about 39% faster on average. | `5fbe6bd`, `b7f5f65` | `overnight/w0-fast-tier` |
| Atomic, idempotent Loop ingestion | `564d213` | `overnight/resume-sdk` / W3 |
| SDK boundary docs: domain adapter, task inputs vs private rewards, v2 contracts | `1d01cb8`, `46320a2`, `30ddbcc`, `322ea73` | `overnight/resume-sdk`, `overnight/w3-adapt-sdk` |
| Hermes Claude workspace authenticated, native header verified | `c4e7501`, `684c162` | `overnight/w2-autoresearch` |
| Cold-start-separated preflight amendment proposal | `0623a3e` | `overnight/w0-orchestrator` |

## Root causes and the fixes already proposed

1. **Fast-tier gate and protected-path misclassification.** The exclusive Python 3.13 fast tier went over its unchanged 180 s deadline. Test-lock violations, including W3's `mkdir -p`, contaminated the early timings. This closed L1 before any study could run.
   - Fix: the atomic schema work (`b7f5f65`) shortens the ARC suite.
   - The deadline and the protected tier manifest stay unchanged.
2. **Duplicate coordinators.** Two W0 coordinator sessions both acted on admission. Each waited for the other's `preflight_ok`, so admission deadlocked.
   - Proposed fix: a single-owner admission guard (`f59fe32` / `e69e136`, unmerged).
   - Proposed fix: a laptop-wide process lock. **No implementation of the lock was found on any branch. It is a proposal only.**
3. **Cold-start latency inside the registered band.** The first preflight call took 66.33 s against a maximum of 62.35 s. That time includes loading the model. The next four calls took 1.55–1.70 s.
   - Proposed fix: the cold-start-separated preflight amendment at `0623a3e`, file SHA-256 `9364e0b4…`.

**Note on the amendment's status.** At 01:26 UTC the ledger records `overnight_autonomy_and_recovery_authorized` against this proposal's hash. The authority cited was the operator's general instruction to work autonomously overnight. W0 then registered a recovery (`ccd24c5f…`) and started lvojhtouu5gede at 01:27. The proposal itself says a general continuation does not amend the procedure.
- No recovery output exists after 01:29 UTC.
- The pod idled until 07:08.
- No `preflight_ok` was ever written.

**Treat the amendment as not yet explicitly approved.**

## Branches

These numbers come from a fetch at the morning close.
- **Base:** `origin/feature/galahad-persistent-memory`.
- **Protected hashes:** all 80 W0 integrity pins match on every head below. None of these branches touch `registry/` or `trust/`.
- **Merges:** none of the worker branches qualified, because every one changes code, scripts, tests or receipts.
- **Focused tests:** nothing was re-run this morning. The "Last recorded focused tests" column is copied from each branch's own receipts.

| Branch | Head | Ahead | Code paths touched | Last recorded focused tests | Merged | Summary for review |
|---|---|---|---|---|---|---|
| overnight/w0-orchestrator | `0623a3e` (7 commits were local-only, now pushed) | 10 | scripts (conductor, identity replay, runpod inventory, v3.2 harmful verify) | 4 temporary-fixture conductor tests | No | Conductor, retirement accounting, v3.2 bounded-rate payload, cold-start proposal |
| overnight/w0-final | `d0fa5ae` | 5 | scripts, tests | conductor tests | No | Earlier closeout pinned to reviewed commits |
| overnight/w0-fast-tier | `b7f5f65` (now pushed for the first time) | 6 | scripts, src (ARC schema) | 13 ARC tests passed, before and after the patch | No | Atomic schema init and fast-tier diagnosis |
| overnight/w1-gate | `46b0f2d` | 1 | scripts (reverify) | 186 replay cells matched | No | Failed v3.2 grid preserved, overnight reverification |
| overnight/w2-autoresearch | `2f2a84f` (1 was local-only, now pushed) | 17 | scripts (cycle, preflight, faithfulness), tests | 41 focused tests on Python 3.13.12 (`8a2cfec`), 43 at the Hermes step | No | Bounded W2 cycle, Hermes wiring, transport binding |
| overnight/resume-admission-guard | `e69e136` (1 was local-only, now pushed) | 17 | scripts (cycle admission), tests | independent review of admission fixes | No | Single-owner, ledger-bound admission guard |
| overnight/resume-a | `134a5b5` | 12 | scripts (Family A registration and replay) | replay reproduction recorded | No | Family A replay and registration, no fresh trial |
| overnight/resume-fast | `638e515` | 10 | scripts, src (arc_execution, governed_learning_v20) | bounded timeouts recorded, not passing | No | Fast-tier timeout diagnosis |
| overnight/resume-report | `9fb7fd6` | 12 | receipts (v2 demos), scripts | — | No | Concurrent preflight receipt reconciliation |
| overnight/resume-sdk | `322ea73` | 9 | receipts, src (SDK) | v2 SDK contract tests | No | SDK v2 contracts and source-pinned replay |
| overnight/w3-adapt-sdk | `acdada1` (1 was local-only, now pushed) | 7 | receipts, src (Loop SDK and adaptation) | SDK tests on Python 3.13 (first overlapping run discarded) | No | L5/L6 synthetic adaptation and SDK |

Only the morning-close branch, `overnight/morning-close-20261017`, was merged into `feature/galahad-persistent-memory`. It contains this report and the snapshots and nothing else. Every push was a fast-forward, with no force.

## Signing queue

**The queue holds one pending entry, and it is unsigned.**

| Field | Value |
|---|---|
| Entry | `gate-v3.2-bounded-harmful-m14-4e2a5addbcc5` |
| Status | `pending_verification` (set at 08:09 London on operator instruction) |
| Signed | No |
| Installed | No |
| Removed | No |

The operator's instruction gave the reason as "harmful-rate 100k-stream check not run". The repository contradicts that. The 100,000-stream bounded-rate run exists at `49bbe7b` (`docs/galahad/evidence/gate-v3_2-harmful-bound/`), and all bounds passed. The queue entry records this correction. The hold stays in place until the operator says which verification is still outstanding, for example an independent W1 replay of that run.

## Evidence

Everything is in [orchestration/morning-close-20261017/](../../orchestration/morning-close-20261017/), with SHA-256 hashes in `index.sha256`:
- ledger, spend, signing-queue and pods snapshots
- the W1, W2 and W3 status files
- W0's untracked `independent-*` outputs
- the amendment proposal
- the RunPod console screenshot

## Before the next attempt

1. Put a `RUNPOD_API_KEY` in the laptop's environment, so that whichever tool is awake can stop a pod. Last night, the only tool that could stop one had hit its usage limit.
2. Explicitly approve or reject the cold-start-separated preflight amendment, using the approval text in the proposal.
3. Merge the admission guard and the laptop process lock, or implement the lock first, before running two coordinators again.

## Addendum, later on 17 October: all worker branches merged

On operator instruction ("push and merge them all", then "update all"), every `overnight/*` branch has been merged into `feature/galahad-persistent-memory` with `--no-ff`. This supersedes the "Merged: No" column in the Branches table above.

Before merging, two pieces of work stranded at the usage-limit stop were committed:
- **W2 `4b9196a`:** every cycle call and remote dispatch is now bound to the coordinator owner's current `preflight_ok`.
- **resume-report `c18aeb6`:** an unrun CPU follow-through script, preserved for the record only.

Five files conflicted. Each resolution kept a superset or the union of both sides:

| File | Resolution |
|---|---|
| `scripts/overnight_conductor.py` | Kept `cb1a8a0`, which is a superset of `cee9c75` |
| `src/nerve_awim/memory_gateway/experience_study_store_v2.py` | Kept the `MAX_RECORDS` bound, the one line that differed |
| `research/leaderboard-20261017.jsonl` | Kept the merged copy, which already held every branch's lines |
| `docs/loop-sdk.md` | Combined resume-sdk's v2 sections with W3's handoff paragraph |
| `scripts/overnight_cycle.py` | Kept both admission checks: the reviewed `require_cycle_admission`, then W2's `require_preflight`. Admission is stricter, not looser. |

Checks on the merged tree:
- All 80 protected pins match.
- `registry/`, `trust/` and `tests/suite_tiers.json` are unchanged.
- The 13 changed test files passed once on Python 3.13.12: 90 tests and 3 subtests.
- No fast or full tier was run.

Every local branch in the repository has also been pushed. The diverged `codex/nerve-adaptation-integrated-20261012` went up as `…-local-20261017`. Nothing was force-pushed. The repository is public.

Item 3 under "Before the next attempt" is now half done. The single-owner admission guard is merged. The laptop process lock is still not implemented.

The attended v5-vs-v4 run requested afterwards did not start, for two reasons. Gate v3.2 is unsigned: it is held as `pending_verification`, and signing is human-only. No `RUNPOD_API_KEY` exists, so a pod cannot be started, driven or verified through the API.
