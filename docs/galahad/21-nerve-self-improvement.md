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
