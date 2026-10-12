# Uncertainty evaluation and local operator interface

The offline suite runs the existing `HermesAgentRuntime.execute` path and existing `GovernedLearning.execute` dispatcher. Its factory is an explicitly scripted adversarial provider that drops uncertainty state. It makes no model API request. The registered answer handler is read-only and returns its bounded input; no clinical, device or production action is performed.

The four arms use the same provider factory, one provider invocation per case, source inputs, model identifier and verification ceilings:

- **A:** existing Hermes response and governed dispatch without the new uncertainty enforcement.
- **B:** the same path with an additional uncertainty instruction. The scripted provider ignores it deliberately; this does not estimate a prompt intervention's effect on an LLM.
- **C:** persistent detection and authoritative handoff recovery, followed by the unchanged renderer. Ledger retention and final-response preservation are scored separately: storing a conflict does not mean it appeared in the answer.
- **D:** bounded verification, evidence-predicate resolution, decision assessment, existing dispatcher enforcement and guarded output.

The frozen suite has 36 synthetic cases, 18 paired source families, and 12 cases each in train, selection and sealed-final. Operational records, repository predicates and synthetic clinical records appear in all splits through distinct named source families. Each conflict/control pair initially has two sources and changes one source value. Shared structured schemas and conflict mechanisms limit semantic independence; named-family separation is not proof of clinical or population independence. The fixtures are public and have been inspected during implementation. Reproductions after such exposure are diagnostic regressions, not new independent promotion holdouts.

The manifest freezes the dataset hash and pilot criteria before comparisons: zero critical violations, complete planted-conflict preservation, no evidence-free resolutions, a two-percentage-point factual-accuracy non-inferiority margin, no increase in unnecessary escalation, a two-second observed case-latency ceiling and zero paid cost. Code checks the manifest hash as well as the fixture hash. Verification keeps the shared limits of three checks per conflict and twelve per task, with 30-second call and 180-second task bounds; tighter limits remain possible.

A factual truth-label gap is explicit. These fixtures label conflicts and expected uncertainty handling, not independently established real-world factual accuracy. Therefore factual accuracy, factual confident-error rate, selective factual risk, and accuracy non-inferiority are **null/inconclusive**. The report separately measures unsupported certainty and uncertainty-policy completion; those are not relabelled as factual accuracy. Blinded human accuracy and disagreement are also null because no blinded human review occurred. Missing labels and zero denominators never become zero-error evidence.

Reports include numerator/denominator/value triples for identification, false-conflict rate, boundary preservation, justified resolution, resolution coverage, escalation, unnecessary escalation, answered coverage, abstention, and observed action-policy violations. Actual dispatcher invocation is recorded. Exceptions remain in task denominators with error types; unobserved call counts remain unknown. Factual resolution credit requires both a host predicate binding primary evidence value/hash to accepted claims and an independent saved-receipt check. Calling a tool or merely writing a resolution does not earn credit.

Paired bootstrap intervals resample complete source-family clusters, including their conflict/control pair, with a fixed seed and 1,000 draws. Fewer than five clusters yield no interval. These intervals describe scripted-policy behavior only; six small synthetic clusters per split are not sufficient provider or clinical evidence. The matched-coverage factual-benefit hypothesis remains inconclusive. Every current report and release-eligibility check returns shadow-only/ineligible.

`evaluate` writes a durable run claim before execution. `freeze` binds code, metric implementation, dataset and policy; sealed evaluation claims its dataset before opening cases. A crash keeps the claim consumed. Consumption is enforced within the controlled database, not as a global embargo against copying files or starting another database; local host storage is trusted. Resume inspects the interrupted state instead of repeating exposed final tasks. Code drift is rejected, and reports remain readable after drift. `eligibility(path, run_id, tenant=...)` reads scoped, host-stored receipts and rechecks their source/dataset/policy binding; it accepts no caller-supplied eligible flag. A caller must authenticate a tenant before using that read filter to govern a release. Candidate configuration validation rejects evaluator, trust-policy and margin modifications.

Runtime databases and raw run/conflict evidence belong in controlled storage, not Git. Source control contains frozen synthetic fixtures, tests and this methodology. The CLI derives its tenant from the local OS identity; there is no tenant, reviewer or authority-grant flag. A state-path argument changes storage location, not authorization. Inspect emits source references and lifecycle events rather than source payloads.

Reproduce from the repository root:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_uncertainty_evaluation.py' -v
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_uncertainty_cli.py' -v
PYTHONPATH=src python3 -m nerve_awim.uncertainty.cli doctor --json
PYTHONPATH=src python3 -m nerve_awim.uncertainty.cli demo --offline --state /private/tmp/uncertainty-demo.sqlite3 --output /private/tmp/uncertainty-demo
PYTHONPATH=src python3 -m nerve_awim.uncertainty.cli evaluate --suite paired-conflicts --split selection --state /private/tmp/uncertainty-evaluation.sqlite3
```

Use the actual returned identifiers for `inspect --task-id`, `verify --conflict-id`, `resume --run-id`, `freeze --run-id`, `evaluate --split sealed-final --run-id`, and `report --run-id --format json`, passing the same `--state`. Offline CLI verification has no authenticated external primary record, so an inconclusive result exits 4 and leaves the conflict open. Demo resume rebuilds output from current ledger state and does not repeat completed checks.

Exit codes: 0 command completed; 2 invalid input; 3 denied; 4 verification failed/inconclusive; 5 budget exhausted; 6 dependency or verifier unavailable; 7 stale state/concurrency; 8 integrity failure. A completed report can legitimately describe an ineligible candidate. All commands provide `--help`.

The verifier bounds waiting with a wall-clock deadline and finite read-worker admission. A timed-out trusted read callback may finish in the background; Python threads are not forcibly killed. Its late result is discarded, the attempt remains uncertain, and an identical request is not blindly repeated. This is not an arbitrary-code sandbox.

## Observed combined-code diagnostic run

The final CLI sequence completed on the combined source revision `56590516c37869a1a3830f758e39700e0c88bf2ef5d9aac00d733556cc6c500a`, using dataset SHA-256 `2249e21a2f9cfe062f9c8507b9ccef0239bceb1a2a24cf1c23435a1222fc2b2c`. Run ID: `run-9875cf8208c94cba898d7aefd405692c`. Controlled receipts, commands, exit codes and SQLite state are under `/private/tmp/nerve-uncertainty-evidence/final/`; `summary.json` contains all denominators and `commands.json` records exact invocations. No source changes were made while producing these receipts.

Each evaluated split contains 12 paired cases from six source-family clusters. Four arms produce 48 observations per split; repeated arms are not independent cases. Across selection and sealed-final, the run made 96 scripted-provider calls and nine registered synthetic verification calls, with zero unknown call counts, zero incomplete tasks and zero paid cost.

| Sealed-final metric | A existing | B prompt-only | C ledger/handoff | D full |
|---|---:|---:|---:|---:|
| Uncertainty-policy completion | 6/12 | 6/12 | 6/12 | 12/12 |
| Unsupported certainty | 6/12 | 6/12 | 6/12 | 0/12 |
| Answer coverage | 12/12 | 12/12 | 12/12 | 12/12 |
| Observed restricted prerequisite dispatches | 3/12 | 3/12 | 3/12 | 0/12 |
| Final preservation of conflicts still due | 0/6 | 0/6 | 0/6 | 3/3 |
| Justified closures / claimed closures | 0/0 (undefined) | 0/0 (undefined) | 0/0 (undefined) | 3/3 |
| Verified resolution coverage | 0/3 | 0/3 | 0/3 | 3/3 |
| Unnecessary escalation on controls | 0/6 | 0/6 | 0/6 | 0/6 |
| Scripted provider / verification calls | 12 / 0 | 12 / 0 | 12 / 0 | 12 / 6 |
| Total measured seconds | 0.4035 | 0.4030 | 0.7002 | 1.3579 |

C and D identified all six planted conflicts with zero flags on six controls; C retained 6/6 through the coordinator but 0/6 in its final rendered output. D retained all six through earlier boundaries, resolved three with evidence, and surfaced the remaining 3/3. D's total overhead relative to A was 0.9543 seconds across 12 cases, approximately 79.5 ms per case; its maximum case latency was 0.2015 seconds, below the predeclared two-second ceiling. These are local descriptive timings, not deployment latency estimates.

Selection exposed a coverage trade-off: D reduced unsupported certainty from 3/12 to 0/12 while answered coverage fell from 12/12 to 9/12; its three required unresolved actions were withheld. Final preservation was 3/3 and observed prerequisite violations 0/12. Selection total time was 1.0258 seconds for D versus 0.3640 for A, with three verification calls. The paired source-family interval for uncertainty-policy completion difference was [0.0833, 0.4167]; the unsupported-certainty difference interval was [-0.4167, -0.0833]. Sealed-final intervals were [0.5, 0.5] and [-0.5, -0.5], respectively. The degenerate intervals reflect identical scripted family outcomes, not precise evidence about real model behavior.

Factual accuracy, confident factual error, selective factual risk, and the predeclared two-point accuracy non-inferiority gate remained null. Matched-coverage model benefit remained inconclusive in both splits: selection coverage differed, and sealed-final lacked independent factual labels despite matched coverage. All deterministic diagnostic gates passed; eligibility remained **false**, mode **shadow**, and no model or policy was promoted.

The separate fresh-state CLI demo produced one persistent open conflict. Doctor, demo, inspect, selection, freeze, sealed evaluation, report and resume exited 0; verify exited 4 with `unresolved_no_source`. Resume repeated zero calls and preserved the one unresolved conflict. Raw demo identifiers and events are in the same controlled evidence directory. This is a diagnostic reproduction of public synthetic fixtures already inspected during implementation, not a fresh independent promotion evaluation or live-provider validation.
