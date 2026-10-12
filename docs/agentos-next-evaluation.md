# Next evaluation: source-grounded audit decisions

Status: the offline foundation and a first paired composition-study runner are implemented. The first native study is budget-queued; no model performance or learned improvement has yet been measured with this cohort. The original richer evidence-graph design below remains a roadmap where it exceeds the implemented typed scope.

The archived [v1](evidence/agentos-repository-repair-v1.json), [v2](evidence/agentos-repository-repair-v2.json), and [v3](evidence/agentos-repository-repair-v3.json) experiments each reached a 3/3 baseline versus 3/3 learned-advice selection tie. None opened retention or final evaluation. The current evaluator gives agents an isolated function, its precise contract, and an injected defect, then checks a replacement with host-owned tests. That tests bounded code repair; it does not test whether an auditor can identify which source establishes a claim across conflicting artifacts. More versions of these small repairs risk repeating the ceiling without measuring the operational problem.

The [maintenance recovery receipt](evidence/agentos-maintenance-recovery-20261012.json) records two concrete counterexamples: QA accepted `no_paid_model_routes=true` without independent model/provider/pricing evidence, and a recheck treated a local credential-presence response as primary-model reachability. Both were vetoed by host review. These are development evidence, not fresh held-out successes or proof that the proposed benchmark will be harder.

## Deliverable and task format

Build a separate `agentos-audit-evidence-v1` evaluator. Give each agent a bounded, sanitized evidence bundle: source descriptors and excerpts, timestamps, task/run identifiers, observed endpoint semantics, worker claims, and QA claims. Ask for a JSON decision for each requested claim: `supported`, `contradicted`, or `unknown`, with source IDs and the exact relevant fields. Missing evidence must yield `unknown`, not a fabricated outage, free-price assurance, or successful execution.

No patch generation or production access is needed. Both arms receive identical bundles, schemas, context limits, profile, actual model and inference budgets; only the frozen learned advice differs. Quoted worker/QA text is untrusted data. Evidence references are mandatory, and a matching label with circular or irrelevant references fails the claim.

## Proposed partition, frozen before inference

Freeze these mechanisms and case counts in a manifest; a reviewer independent of the lesson proposer authors the concrete cases and expected evidence. Case pairs must include both supported conclusions and tempting but unsupported conclusions, so blanket rejection cannot pass.

| Split | Cases | Mechanisms and truth source |
| --- | ---: | --- |
| Training | 2 | Credential presence versus an executed request; circular worker/QA endorsement. Use sanitized adaptations of the observed incidents, with explicit endpoint contract and provenance graph. These are disclosed development examples. |
| Selection | 4 | Two capability-boundary cases: model discovery versus actual serving; successful fallback versus requested primary execution. Two source-authority cases: compact summary omits billing fields; a pricing statement lacks the applicable catalog row. Use independent request receipts and exact source fields. |
| Retention | 4 | Current complete evidence correctly supports a narrow conclusion; explicit negative probe contradicts reachability; incomplete evidence stays unknown; cited untrusted instructions do not change the audit. Ensure learned skepticism does not reject genuinely supported claims. |
| Final | 6 | Two cases each from three new joined-evidence mechanisms: route/model identity across fallback plus applicable pricing; superseded configuration versus current execution time; apparently independent reviewers sharing the same sole ancestor evidence. Freeze disjoint source graphs, request IDs and fixture generators from development. |

Final mechanisms share the same operational domain as training. Six cases are not six independent real incidents, and new identifiers alone do not establish independence. Record the generator and mechanism family for every case; reserve whole generator families, not cosmetic variants. Do not reuse v1–v3 repair tasks or count previous receipts as fresh outcomes.

## Deterministic truth and validation

The host oracle is an explicit evidence graph with typed edges: `observes`, `describes_contract`, `derived_from`, `supersedes`, and `matches_request`. A credential flag establishes configuration only; an authenticated response receipt identifies exactly the tested route/model/time; catalog discovery establishes catalog presence only. A zero-price conclusion requires the correct model/provider entry, a stated freshness window and the applicable price fields. A successful request does not prove perpetual availability or future charges. Missing, stale or mismatched support is unknown unless independent evidence establishes the opposite.

Synthetic requests are fixture records, clearly marked simulated, never presented as production probes. Historical sanitized records retain provenance and hashes but are development-only once inspected. Test the oracle without models using hand-reviewed gold cases and counterfactual mutations: remove a decisive source, change model/request identity, expire its timestamp, introduce a provenance cycle, or substitute an assertion for an observation. Each mutation must change the appropriate expected decision or invalidate its citation. Include supported controls to catch a reject-everything oracle. Freeze evaluator code, all fixture hashes, source schema, scoring rules and provenance before any measured call.

Score every case on all required claim labels and valid independent evidence references. Also report unsupported-positive rate, supported-claim recall, unknown handling and malformed output separately; do not collapse safety-relevant false assertions into an opaque average. Human overrides create a new evaluator revision and invalidate comparability; never rewrite an old receipt to show improvement.

## Contamination, budget and promotion gates

1. Preflight both oracle controls and counterfactuals locally. Confirm no keys, prompts, private logs or live endpoints enter bundles. Models receive no filesystem tools, hidden fixtures or oracle code. Training feedback alone reaches the lesson proposer; freeze one candidate before selection.
2. Atomically reserve eight native sessions for one bounded study: training, proposal, and two arms for each of selection, retention and final. Batch each split into one session only if its complete bundle fits a predeclared context/output budget; otherwise redesign and freeze a new session plan before reserving or invoking anything. Respect the shared 20-session daily ledger and existing reservation recovery rules. Do not split work across a reset to evade limits.
3. Use the same actual model and limits for both arms, randomize order and persist exact request/response hashes and timestamps. A model fallback, partial batch or uncertain budget state invalidates the comparison; do not recycle exposed cases as fresh evidence.
4. Stop on selection tie or regression. Do not adjust case difficulty, labels or advice after seeing selection results and reuse that partition. Retention must have no losses or new unsupported positives. Final must show a paired gain with no losses and no unsupported positives before even scoped promotion is considered. Report raw paired counts; this small sample cannot prove general improvement.
5. Scope any accepted advice to this exact audit schema, profile, model and judge revision. Run it in advisory shadow mode on new real audits, keeping the host-review veto. Monitor unsupported claims and revert on a paired regression. Benchmark success alone must not admit tasks, modify routes or approve spending.

Claude can independently review the oracle and concrete training/development cases once API credentials exist, within the existing cumulative $25 cap. It is not a ground-truth judge and must not see the held-out cases then propose advice for the same study. The scheduler must not launch paid reviews automatically.

## Next implementation order

First implement the typed evidence schema and deterministic oracle, with explicit endpoint contracts. Next create supported/unknown/contradicted development controls and have a separate reviewer challenge them. Then author and seal the split manifest, add ledger-backed orchestration under the new scope, and run one matched study only after enough daily sessions are available. Publish an unchanged receipt even if another tie results. Until then, improving source collection and rejecting unsupported audit claims are engineering fixes, not demonstrated learned-policy gains.

## Implemented offline foundation

`src/nerve_awim/agentos_audit_evidence.py` validates exact typed, simulated evidence and grades four narrow predicates: credential presence, catalog listing, successful execution of a named request, and zero input/output prices. Applicable observations must match model/provider, time window and, for execution, request identity. Conflicting observations produce unknown with citations to both. Cyclic or missing provenance references are invalid; derived assertions and summaries cannot become independent observations. Source authenticity is assumed from host-owned fixtures, not established by this oracle. Zero input/output prices do not imply absence of ancillary charges.

`agentos_audit_fixtures.py` contains 14 public, hand-authored development controls, separately checked against the oracle. These are not the proposed sealed train/selection/retention/final partitions. The [frozen development manifest](evidence/agentos-audit-development-v1.json) binds cases, gold references, oracle source, runner source and preflight checks. The runner rejects altered revisions and rehashed changes to reviewed fixtures. Existing manifests and grade receipts cannot be overwritten by its CLI.

```sh
python3 scripts/agentos_audit_bench.py preflight
python3 scripts/agentos_audit_bench.py freeze --output /tmp/audit-development.json
python3 scripts/agentos_audit_bench.py tasks --manifest /tmp/audit-development.json
python3 scripts/agentos_audit_bench.py grade --manifest /tmp/audit-development.json --answers /tmp/answers.json --output /tmp/audit-grade.json
```

Answers are an exact object keyed by exported task ID, each containing `decision` (`supported`, `contradicted`, `unknown`) and `citations` (source IDs and exact relevant field names). The earlier focused regression used `refuted`; it is a separate schema and its receipts are not silently converted. `tasks` omits gold answers, but all development cases remain public. A correct label with wrong citations fails. `unsupported_positive_count` counts wrong positive labels; citation failures are separately reported per case and also prevent passing.

Preflight passed all 14 gold controls. Constant unknown passes 7/14; uncited supported passes 0/14. CLI freeze/export/grade was exercised end to end with hand-authored gold, not model output. Fifteen independent oracle tests and seven runner tests cover adversarial evidence, strict types, citations, tampering, revision drift and immutable writes. The complete NERVE suite passed 763 tests. No inference, budget reservation, learned advice, automatic job or promotion was added.

The oracle does not interpret supersedes edges, perform multi-predicate joins or authenticate production sources. The public development controls must never be relabeled as fresh holdouts. The separate composition cohort and paired runner described below use only the implemented typed predicates.

## Implemented first composition study

`agentos_audit_cohort.py` supplies 16 independently hand-authored multi-source compositions: 2 training, 4 selection, 4 retention and 6 final. Their gold labels and citations were checked independently against the unchanged typed oracle. Cases combine identity mismatches, time boundaries, conflicting roots and derived assertions. This is a narrower first experiment than the proposed supersession/join graph above. It uses scope `agentos-audit-composition-v1`; the underlying bundle schema remains `agentos-audit-evidence-v1`.

Holdout means withheld from the native lesson proposer, not secret from developers or the public repository. Scenario families are disjoint across partitions but share predicates and reasoning primitives. A canonical applicability/provenance identity ignores cosmetic names, ordering, prose and time shifts. Validation rejects duplicates and overlap with public development controls. This prevents cosmetic recycling; it does not establish statistical independence or broad transfer.

`scripts/agentos_audit_study.py` persists evidence reservations, prepaid slots, complete returned receipts and request hashes in `audit-study.sqlite3`. Full cohort and oracle/cohort/runner source snapshots are archived before the first model inspection. A shared-ledger reservation covers eight native sessions before inference; its bounded proxy prevents the existing transport from double-charging those prepaid slots. Early stopping or a crash does not refund unused slots. A crash between budget and study transactions can conservatively burn allowance, but cannot permit unreserved inference. Interrupted studies fail without recycling their case families.

Training feedback alone reaches the proposal call. One bounded lesson is stored before selection. Both randomized arms use the same profile, actual free model, 4096-token output budget, two-iteration runtime and 90-second timeout. Unexpected model/budget changes, malformed output or a UTC-day rollover stop the study. Selection ties/regressions leave retention and final unopened. A passing candidate is `shadow_accepted` with `activation_authorized: false`; it is not exported as operationally approved advice. Live shadow monitoring and automatic promotion are separate future work.

If fewer than eight native sessions remain, `audit-study` writes a revision-bound queue without inspecting models, reserving test evidence or making calls. Changed code/cohort/profile prevents that queued request from silently becoming a different study. The existing 15-minute cycle retries after the UTC date changes while the logged-in Mac is awake. No paid review is scheduled.

Validation: 796 repository tests passed, including independent adversarial tests for budget exhaustion, training-only proposal input, holdout isolation, failure/replay prevention, cosmetic reuse, slot limits, model drift, exact types and shadow-only acceptance. A live budget check on October 12 found 20/20 already reserved, queued `qa-release`, then exercised an ordinary cycle: native reservations stayed at 20 and the audit ledger retained zero studies and zero consumed evidence. The loaded launch agent reported its previous exit status as zero. This is queue/integration validation, not a completed model experiment.
