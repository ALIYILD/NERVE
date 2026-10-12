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
| CCE-specific tests included in the full suite | **151 passed**, including local artifact/renderer/receipt checks, frozen datasets, missing calibration and prior host governance contracts |
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
adaptation object is attached; attached-module errors still propagate. A follow-up
regression test also verifies that a persisted, scoped adaptation task is denied
when its coordinator is missing. Unregistered tasks remain usable without the
optional module. After the initial repair and required test permission, the host
wiring suite passed. Existing
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
| 13 Recursive improvement | Partial | Host cycle → pending memory → explicit operator CLI approval, rejection and baseline rollback tested; no automatic live cycle dispatch, retained-capability benchmark or production canary connection |
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
