# Loops 11–12 implementation evidence

Status: focused acceptance passed; final aggregate repository regression is owned by the integrating agent. Final smoke receipts regenerated after runtime integration hardening.

Integration: `arc_evaluation.py` calls the existing `GovernedLearning`-based `arc_workflows.run_workflow`; new `arc_*` evaluation tables share the supplied SQLite path. No production release is activated.

Files: `src/nerve_awim/arc_evaluation.py`, `tests/test_arc_evaluation.py`, `docs/arc/smoke-v1.json`, `smoke-v1-manifest.json`, `smoke-v1-report.json`, `candidates-v1-report.json`, and `evaluation.md`.

Observed focused gate: `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_arc_evaluation.py' -v` — 13 tests passed in 17.962 seconds after runtime integration hardening. The first runs detected concurrent source-revision changes and correctly refused resuming an experiment against modified code; no acceptance threshold was loosened.

The first actual three-arm run produced development 30/30 for all arms; validation 9/15 baseline and structured versus 15/15 full; locked test 12/15 baseline and structured versus 15/15 full. Unsupported successes were 6/15 then 3/15 in the baseline/structured validation/test splits, and zero for full. Policy violations were zero. These results identify absent-result verification as a deterministic software behavior improvement. They are not LLM-learning or clinical-performance evidence. A subsequent metric review corrected baseline recovery reporting: the baseline does not actually restart, so it must not receive recovery credit merely because the first execution succeeded.

Candidate experiments are limited to three registered strategies. After independent review fixed an ablation confound, candidate comparisons use full verification in both arms. Default and evidence-first tie and are rejected for no gain; conservative is rejected for nine validation task-level regressions against full verification. No candidate is selected. Definitions bind actual observed development episode IDs, dataset and source versions. Candidate changes cannot include evaluator, policy or budgets. Tests cover mutation attempts, regressive rejection, budget exhaustion, interruption, concurrent ownership and consumed holdout reuse.

The release report's test fixtures are now exposed. Reproducing the smoke suite after final implementation hardening remains useful regression evidence, but it is not a fresh independent promotion holdout. A subsequent promotion experiment requires a new reviewed suite. All inference is deterministic/offline, and paid cost is zero.

Final evaluated source revision: `01a5ff1c3c1a1d0b6fbba508033b768d9f31875da4a68609e57091ebc99d85a6`. Recovery metrics: baseline 0/3, structured 3/3, full 3/3. Baseline and structured test correctness 12/15; full 15/15. These are regression reproductions of the already-exposed synthetic suite, not a fresh promotion holdout.

Independent parent review additionally corrected candidate failure evidence (only actual failed outcomes, never correct abstentions), bound the revision to dispatcher/operations/verifier sources, and made the policy metric reject unsafe effect actions independently of self-reported permission. A zero-failure run generates no candidates. These are evaluator corrections, not threshold changes or demonstrated learned improvements.

Final candidate outcomes: default rejected (tie, zero regressions), evidence-first rejected (tie, zero regressions), conservative rejected (nine task-level regressions: three lost successful inventories and six unnecessary action changes on absent-result cases). Selected candidate: none. The earlier three-regression count used the transport-only ablation as comparator and is superseded.
