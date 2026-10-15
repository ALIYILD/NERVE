# NERVE's first self-improvement study

The research target is NERVE's own memory-selection performance. This work adds a measured policy candidate and a bounded comparison against the actual integrated default; it does not claim model-weight learning or a scientific discovery outside this synthetic software experiment.

## Concrete defect and candidate

The current ranker uses recent per-memory Beta(1,1) outcome means. With a three-outcome window, two memories that have each failed three times tie at0.2. The existing relevance tie-break can keep selecting the same failing memory forever, even if the alternative would now succeed. A training-only regression reproduced four repeated selections of the same failing strategy.

The optional `tie_break="least_recent"` policy breaks exact utility ties by least recent judged use, then existing relevance. It changes neither the candidate pool nor approval/scope checks. Higher utility still wins. Unseen candidates retain neutral utility. This is limited exploration on ties, not arbitrary new-tool creation or general reinforcement learning. The default remains `relevance` until evidence and host review justify a change.

`VerifiedOutcomeLearning` accepts the host-selected policy. Automatic run configuration freezes it, preventing silent policy changes during restart. Old run records without a tie policy migrate atomically only to their prior implicit `relevance` semantics when every other setting matches; consumed budgets are preserved.

## Frozen experiment

Six configurations combine windows3/10/20 and relevance/least_recent ties. The current baseline is3/relevance, not the older standalone ranker's20 default. Each trial uses an isolated SQLite ledger and the same two registered tools. Temporary fixture memory IDs and timestamps are equalised across arms to prevent random initial ranking from masquerading as improvement. Production identifiers/timestamps are untouched.

Stationary, abrupt-change, recurrent-change and mixed schedules use disjoint training, validation and holdout seeds and opaque task payloads. The protocol records schedule generation, dataset hashes and configuration-selection rules. Candidate selection uses validation probe successes, retaining the baseline on ties; it is frozen before any holdout arm runs.

Each arm executes20 feedback tasks and5 subsequent probes. Adaptive feedback prefixes use the actual automatic runner. Probes use strict read-only agent execution and cannot call learning. The entire utility table is hashed before/after probes and must remain identical. Holdout arms receive their own matched online adaptation prefix; it would be incorrect to say the entire holdout has no feedback. Only probe outcomes are withheld from learning.

Held-out comparisons include current adaptive baseline and both fixed registered strategies. All execute the same number of actual tool pipelines and share the same information available to those tools. CPU timing includes differing learning/gateway overhead, which is reported separately; it is not LLM inference latency. No paid model cost, energy savings or GPU result is invented.

The existing paired-statistics implementation supplies descriptive paired deltas and a seed-cluster bootstrap. Its legacy `no_memory`/`with_memory` field names map to current adaptive baseline/selected candidate, explicitly labelled in the report. Five synthetic seed clusters and four constructed task families do not establish scientific or clinical generalisation, regardless of p-value.

A candidate is proposed for host review only if validation selected a different policy, held-out total accuracy improves and no tested scenario regresses. Otherwise the recommendation is to retain the baseline. No automatic production activation or source rewriting occurs. All fixtures are public and reproducible, not externally sealed; do not repeatedly tune against this holdout and call it independent evidence.

## Reproduce

```sh
cd /Users/aliyildirim/nerve-galahad
PYTHONPATH=src .venv/bin/python benchmarks/memory_self_improvement.py --output /tmp/nerve-self-study.json
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_memory_exploration.py -v
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_memory_self_study.py -v
.venv/bin/python scripts/verify_galahad.py baseline
```

The output path must not already exist. Protocol and selected-policy hashes let reviewers identify exactly what was measured. The full study is fixed and bounded; it does not start a continuous scheduler or give agents permission to assign rewards or approve memories.

## Measured result and decision

Code: `a5f83c69e50743bb38b640d6e3be9582413272d4` on `feature/galahad-persistent-memory`. Full suite: **1,093 passed** in54.233seconds, zero failures/errors/skips. This includes six exploration/compatibility regressions and eight study-contract tests. Compileall and whitespace checks passed. No remote CI, push, PR, merge, deployment or model-weight training occurred.

The first actual full study executed4,400 tool pipelines in176 isolated trials. It selected window10/relevance from validation (34/40 probes), versus current window3/relevance31/40. The least-recent variants tied their corresponding windows on validation, so the unchanged relevance policy won the preregistered tie rule.

| Held-out arm | Correct probes /100 |
|---|---:|
| Current default: window3/relevance |73|
| Validation-selected: window10/relevance |73|
| Fixed lower-only tool |55|
| Fixed trim-lower tool |45|

Selected versus current produced five paired wins and five paired losses. Scenario deltas: stationary0, abrupt0, mixed+3, recurrent−3. Descriptive seed-cluster95% interval for accuracy difference:−0.09 to+0.09; exact descriptive paired p=1.0. **Recommendation: retain the current default.** The selected configuration had no total gain and regressed on recurrent tasks. No configuration was promoted.

Every frozen probe passed the unchanged-utility snapshot check. All arms had equal25 tool executions per trial; total study wall time was100.870seconds on Python3.10.0/macOS x86_64, with other regression work sharing the host during part of the run. Those CPU times are execution evidence, not a representative latency/speedup benchmark. No inference-token, energy or monetary-cost improvement is claimed.

The training-only equal-failure regression separately demonstrates that least-recent ties escape a specific lock-in. The broader study did not establish an aggregate advantage for that candidate; it remains explicitly opt-in. This distinction is essential: fixing one constructed failure is not proof of broadly better adaptation.

The result shows why NERVE needs comparative testing: a longer window looked better on validation but traded mixed-task gains for recurrent-task regressions. Future policy research needs a newly frozen protocol and untouched evaluation corpus, rather than tuning against this now-observed holdout. Real scientific tasks, actual model integrations and independent domain evaluation remain future work.

Evidence: [complete preregistered study and trace](evidence/self-improvement-study-v1.json), [test validation](evidence/self-improvement-validation.json). The following documentation commit does not change the tested executable code.

Added files: `memory_gateway/self_study.py`, `benchmarks/memory_self_improvement.py`, exploration/study tests and this report. Modified existing `adaptive_memory.py`, gateway learning/automatic-run configuration, verification groups and README. Existing ledger, gateway, agents, independent outcome evaluator and paired-statistics engine are reused.
