# CCE implementation and verification status

Verified 2026-10-12 from base `a4942ea`, initially in the isolated
`codex/cognitive-cue-engine-20261012` worktree. The follow-up adds
[installed-host wiring](host-integration.md) for application to the NERVE checkout.
The CCE publication excludes unrelated uncommitted adaptation changes. No live
operational cue has been enabled and no model or clinical deployment has been performed.

## Observed checks

| Check | Observed result |
| --- | --- |
| Complete Python suite after host wiring | **1,027 passed**, 35.928 seconds |
| Integrated suite with published world-model work and adaptation guard | **1,080 run, 1,079 passed, 1 skipped**, 77.911 seconds |
| Continued host/discovery/readiness integration, full suite | **1,109 run, 1,108 passed, 1 skipped**, 176.374 seconds |
| Local model/dataset/evaluation integration, full suite | **1,149 run, 1,148 passed, 1 skipped**, 93.969 seconds |
| Durable dataset reservations and cutover, full suite | **1,179 run, 1,178 passed, 1 skipped**, 143.784 seconds; final readiness snapshot metadata also passed its eight focused tests |
| CCE-specific tests after durable dataset integration | **181 passed**, including relabeling, split movement, transaction rollback, restart, legacy cutover and prior local/host contracts |
| Retained-capability gate integration, full suite | **1,221 run, 1,220 passed, 1 skipped**, 77.308 seconds |
| CCE-specific tests after retained-capability integration | **223 passed**, including schema compatibility, pre-holdout ordering, persistence, scope cutover, evidence tampering and release recomputation |
| Scheduled CCE job integration, full suite | **1,242 run, 1,241 passed, 1 skipped**, 69.343 seconds |
| Scheduled job focused checks | **21 new tests passed**: 10 durable queue tests and 11 autoresearch/bridge tests; 15 existing autoresearch tests also passed |
| Evaluator-feedback discovery integration, final full suite | **1,259 run, 1,258 passed, 1 skipped**, 81.552 seconds |
| Feedback-focused additions | **17 new tests passed**: 11 scoped context/validation, five discovery/cycle integration and one queue redaction test |
| Local scheduled adapter integration, full suite | **1,276 run, 1,275 passed, 1 skipped**, 68.727 seconds |
| Local protocol/registry additions | **17 new tests passed**: six response-contract and 11 registry/oracle/budget tests |
| CPU timeout repair, source and installed CCE suites | **273 passed** in each checkout; six new timeout/deadline tests; source 8.000 seconds, installed 7.510 seconds |
| Structured-output repair, source and installed CCE suites | **275 passed** in each checkout; source 6.518 seconds, installed 10.036 seconds; exact request schema and profile/schema drift coverage |
| Integrated restricted-environment run after concurrent main merge | **1,352 run**, 36 failure reports / three errors / one skip, 178.012 seconds; failures were blocked macOS sandbox probes and localhost HTTP test servers; unrestricted rerun required |
| Final integrated unrestricted rerun | **1,352 run, 1,351 passed, one skipped**, 188.359 seconds; seven Node checkpoint tests and offline CCE commissioning also passed |
| Continuous research memory/intake and v3 cohort | **1,366 run, 1,365 passed, one skipped**, 146.387 seconds; focused 19 scheduler/research and 46 cohort tests passed; software and independently reviewed fixture evidence, not a live gain claim |
| Citation contract, training-error feedback and pending queue review | **1,376 run, 1,375 passed, one skipped**, 96.036 seconds; 56 focused cohort tests passed; existing consumed studies remain closed |
| Node checkpoint discovery | **7 passed** |
| `git diff --check` | Passed |
| Offline commissioning CLI | 30 paired tasks / 60 fixture calls, zero external provider calls; candidate rejected, no active cue, pending memory export |
| Real local instruction smoke | Four measured Ollama calls, two arithmetic pairs, both arms 2/2; 184 input / 12 output tokens; zero errors/truncations; ineligible for promotion |

Commands used:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -q
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_cue*.py' -q
node --test tests/test_checkpoint_discovery.cjs
PYTHONPATH=src python3 -m nerve_awim.cue_cli demo --output docs/cce/offline-demo.json
git diff --check
```

The full suite needs permission to invoke its existing nested macOS sandbox.
The initial restricted run had 36 failures and 60 errors, caused by unavailable
nested sandboxing and the starting commit's unconditional import of an absent
optional `adaptation` module. The ARC repair invokes that hook only when an
adaptation object is attached; attached-module errors still propagate. After this
repair and the required test permission, the final full suite passed. Existing
ARC action, approval and verification logic is otherwise unchanged.

Independent review also found and repaired persisted cue-version mutation and a
direct-experiment clinical-label bypass. Regression tests cover both. Later checks
cover executed cue/arm receipt binding, permanent study reservations, stale
inference configuration, expiring evidence, revoked approvals and durable rejection
after a failed study.

Host integration adds tested `cce-status`/inspection/revocation commands, separate
host-selection and worker-application receipts, uncued research controls, and
fresh-only feedback/memory export. The status command was exercised without any
provider call and reported `enabled: false`, `reason: not_configured`.

The continued implementation exposes trusted host discovery and cycle methods,
operator approval with current-generation/profile checks, provider-free installed
profile inspection, and recomputed release readiness. The observed installed
`qa-release` profile has a clean identifiable Hermes checkout and template, but
does not attest model or tokenizer revisions. No provider calls or cue activation
were performed. The new release builder consumes trusted host observations; it
does not turn uploaded JSON assertions into staging proof or deployment permission.

The [local research adapter](local-research.md) adds a verified installed GGUF,
server identity checks, an explicitly supported Qwen instruction renderer and
bounded measured generation through the existing experiment interface. A strict
frozen-dataset loader checks global content and split-family overlap. Missing
confidence stays null and blocks promotion; measured token counts include coverage.
Historical reports without usage fields retain their original digests. The first
diagnostic local run failed on its fourth generation; both that incomplete receipt
and the successful transport repair are retained. Neither is paper reproduction,
an efficacy claim or production-worker attestation.

Dataset-aware cycles now reserve content and family identities as well as task IDs
before discovery. Renaming IDs/source/answers cannot recycle known holdout content.
The first bound reservation upgrades its tenant/agent scope: ID-only downgrade and
legacy evaluation/approval/serving are blocked. The guard survives contract changes
within that scope, preserves historical records and exposes read-only status.
Cross-agent semantic deduplication and legacy content backfilling remain outside
the available evidence; changed paraphrases still need honest family annotation.

Retained-capability screening now runs between selection and untouched holdout
for schema 2 datasets. Its independent verdict is persisted and revalidated at
holdout admission, approval, routing and release review. Scope cutover survives
contract changes; old candidates cannot bypass the new gate. All 42 additional
tests use contract doubles, not measured model-effectiveness evidence. No real
retained-capability benchmark or operational activation is claimed.

## Loop ledger

“Verified” below means the stated local software gate, not live model effectiveness
or clinical assurance. The complete objective is **not** claimed complete.

| Loop | Status | Evidence / outstanding work |
| --- | --- | --- |
| 01 Discovery | Verified | [Architecture inventory](architecture.md), real interfaces and dependency boundaries |
| 02 Paper reproduction | Blocked | [Pinned handoff manifest](reproduction-manifest.json); no GPU host, weights, dataset/grader pins or approved compute budget |
| 03 Core | Verified | Immutable registry and persistent version identity, profiles, no-cue routing; core and governance tests |
| 04 Discovery | Partial | Bounded multi-candidate Hermes collection, source-preserving paper imports, exact-content deduplication and host cycle tested; author beam search/entropy screening not implemented in NERVE or reproduced |
| 05 Profiling | Partial | Hermes inspection plus verified local GGUF/tokenizer artifact and Ollama executor identity; production worker attestation and exact tokenizer boundary IDs remain unavailable |
| 06 Evaluation | Partial | Strict source-bound dataset loader, measured per-call token coverage and unknown-confidence handling tested; real local arithmetic transport measured, paper benchmark extraction/grading still outstanding |
| 07 Routing | Verified | Actual Hermes instruction boundary tested; unsupported prefixes fall back; provider-specific native prefix transport remains outside this host contract |
| 08 Hermes | Verified | Existing roles, fresh sessions, JSON/no-tools guarantees, bounded telemetry and fail-closed policy errors tested with contract doubles |
| 09 JEV | Verified | Existing transport configuration, numeric aggregate-only requests and advisory probabilities tested; no live JEV call or measured calibration claim |
| 10 Memory | Verified | Existing authority/database/audit and pending trusted-memory export; cross-scope denial, persistence, expiry and outcome revocation |
| 11 Safety | Verified | Clinical/high-risk exclusion, permission gates, cue/receipt tampering and scoped approval tests; clinical deployment remains prohibited |
| 12 Performance/cost | Partial | Local context/output/call limits, measured tokens, durations and zero external fees; compute cost unmeasured and no performance benefit demonstrated |
| 13 Recursive improvement | Partial | Dataset-bound host cycles with durable ID/content/family reservations, safe legacy cutover, pending memory and operator approval tested; persisted retained-capability screening tested; durable jobs join the existing scheduled loop but lack a trusted live adapter; no real retained-capability benchmark or production canary connection |
| 14 API/docs | Verified | Local Python APIs, offline CLI, runbook, full fifteen-loop specification and Claude Code prompt |
| 15 Staging/deployment | Blocked | Offline release manifest recomputes eligibility and identifies missing staging/rollback receipts; no validated live profile, eligible live candidate or controlled traffic evidence |

## Measured fixture outcome

Both arithmetic fixture arms answered 30/30 tasks correctly. Their accuracy delta
was zero; descriptive McNemar p was 1.0. Synthetic evidence and no improvement
therefore prevented promotion. Latency comparisons vary between fixture runs.
These results describe deterministic fixture plumbing only; the separate measured
local-model run is documented above.

The [machine-readable demo receipt](offline-demo.json) includes the full paired
scores, rejection reasons, conservative uncertainty interval, local routing timing
and SHA256 hashes of the CCE source files. No raw task instructions, expected
answers or generated responses are stored there. Timing can vary between runs.

## Concrete handoff

1. Provision an approved GPU research host and budget; resolve missing immutable
   model/tokenizer/dataset/grader/container fields in the reproduction manifest.
2. Build and validate a native response-prefix adapter separately from the existing
   Hermes instruction adapter. Verify complete rendered prompt tokenization.
3. Execute the [source-backed protocol](reproduction.md), including no-cue and
   published cue arms and independent grading. Attach complete real receipts;
   unit fixtures cannot satisfy that gate.
4. Connect host-authenticated evaluator identities and content/family deduplication.
   Local identifiers and capability objects are not remote authentication.
5. If a live candidate qualifies, prepare an actual staging target and run the
   existing deployment review/canary process. Approval of a cue never grants tool,
   provider or clinician permissions. Keep the current no-cue deployment until
   those gates have evidence.

The [master Claude Code prompt](claude-cli-prompt.md) and [complete implementation
plan](implementation-plan.md) provide the continuation instructions. Missing
external evidence must stay visible rather than being replaced with simulated
success or a blanket “15/15 complete.”

## Scheduled CCE job boundary

The durable job path joins the existing autoresearch tick and host lock, reuses
`autoresearch.sqlite3`, and leaves operator approval separate. Its installed
adapter registry supplies no live callbacks by default, so scheduling does not
imply provider dispatch. Specifications cannot import callbacks. A job is claimed
before execution and interrupted work is sealed without automatic replay.

Schema 2 jobs require at least 30 untouched holdout pairs plus selection and
regression, costing at least 65 model calls including discovery. The native
Hermes 20-call daily cap, unavailable immutable model/tokenizer identity and
missing calibrated confidence/complete measurement receipts remain live blockers.
The local Ollama transport smoke also lacks answer confidence and worker
attestation. No live scheduled CCE experiment or automatic activation is claimed.
The full suite and focused queue/integration checks above passed with trusted
contract doubles. They establish software behavior, not live model effectiveness.

At the inspected installation, autoresearch was enabled for `qa-release`, with
zero native sessions remaining in that day's budget. No live CCE configuration
or queued CCE jobs had been installed. This is an installation snapshot, not a
claim that the new scheduled path has produced model evidence.

## Feedback-to-discovery evidence boundary

The host can freeze bounded exact-scope/profile/task evaluator history and supply
it to the existing research callback. Snapshots contain revalidated cue text and
hashes plus bounded aggregate feedback, with no candidate/episode/task IDs,
answers or heldout metrics. Cycle audit stores the snapshot digest and aggregate
metadata rather than raw cue text; no standalone history CLI is added. Empty
history retains the original discovery payload.

The source label is `trusted_evaluator_feedback`, deliberately not an assertion
of operational cue application. Existing feedback rows lack durable worker
application provenance and may include a candidate revoked before approval.
Counts are observational, not causal, and never authorize release or restore a
revoked cue. This implements a feedback input path; no measured recursive model
improvement or new live experiment is claimed. Final integration test results
remain the coordinator's separately recorded verification.

Historical `cue_digest` is SHA256 of the exact UTF-8 cue text, not the
metadata-bound `Cue.content_hash` used by experiment receipts. Duplicate text
keeps only the most recent eligible candidate's latest 64 observations; counts
are not pooled across versions. The snapshot digest binds the frozen in-memory
discovery invocation. No full snapshot is retained for later reconstruction.
Cue safety validation is a bounded instruction filter, not a privacy classifier;
hosts must keep sensitive data out of historical cue text.

The first feedback integration run exposed one legacy discovery compatibility
failure: creating governance state when no feedback existed. The host now checks
for scoped feedback read-only and retains the prior no-bootstrap behavior when
none exists. The final full suite above passed after that repair.

### Live commissioning supersedes earlier installation snapshots

Local research is now enabled on the installed host, and both frozen CCE jobs
actually ran. Both failed on their first evaluation timeout and remain consumed;
no candidate was activated. The timeout repair is installed and published.
See [the commissioning record](local-live.md#live-commissioning-13-october-2026-europelondon)
for measured failures, diagnostic limitations, the existing scheduler and the
successful task-local adaptation run. Earlier paragraphs describing an empty
queue or no configured profile are historical snapshots.

The opt-in local handoff protocol now supplies model-self-reported probabilities
with independent host grading, source/model identity checks and a separate durable
80-call daily ledger. Two public procedural datasets were frozen before inference.
Tests above establish software behavior; measured commissioning outcomes belong
in [local live research](local-live.md), not in fixture effectiveness claims.
