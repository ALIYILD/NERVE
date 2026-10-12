# Research-driven discounted outcome learning

## Sources and implementation hypothesis

Internet research on 12 October 2026 examined these primary sources:

- [Qi, Wang and Zhu: Discounted Thompson Sampling for Non-Stationary Bandit Problems](https://arxiv.org/abs/2305.10718). The authors study discounting within Gaussian-prior Thompson sampling under abrupt and smooth changes. This motivates reducing old evidence weight; our deterministic Beta-mean heuristic is not their algorithm, and their regret guarantees do not transfer.
- [Liu, Van Roy and Xu: Nonstationary Bandit Learning via Predictive Sampling](https://proceedings.mlr.press/v206/liu23e.html). The authors explain that information loses usefulness at different rates and standard Thompson sampling can perform poorly in changing environments. This argues for measuring stationary and changing regimes separately, rather than assuming exploration always helps.
- [Shinn et al.: Reflexion](https://arxiv.org/abs/2303.11366). Their agents keep linguistic feedback in episodic memory without weight updates. NERVE already has independently verified outcome memory. This change keeps the host evaluator authoritative; it does not automatically approve model-generated reflections.

Code inspection found that existing recent-window scoring weights every observation in that window equally. Optional last-use decay only shrinks the combined score toward neutral. The new hypothesis is that weighting each judged observation by its age can respond better to changing requirements.

## Frozen experiment design

Candidate ranking uses `(1 + sum(weight * success)) / (2 + sum(weight))`, with weight `2 ** (-scope_local_age / discount_half_life)`. The prior stays fixed. Only authorised records may be ranked. Scope-local ages count judged feedback within the same tenant, agent, context and evaluator revision. Defaults remain unchanged; this is an opt-in data-only policy. Per-observation discount and last-use decay are mutually exclusive to avoid ambiguous combinations. Durable run configuration records the choice; legacy runs migrate only to the disabled default without replenishing their budgets.

The v3 study uses fresh training seeds 4001/4002, validation 5001/5002 and ten holdout seeds 6001–6010. Baseline: window 3, relevance tie breaking, no discount. Six candidates: windows 3/10 × half-lives 1/3/10. Existing strict validation improvement, training nonregression and per-scenario validation nonregression gates remain in place. At most 272 trials / 6,800 tool calls, two generations, and one final heldout comparison. Every trial contains 20 online feedback executions and five frozen probes. Selection cannot use holdout outcomes. Actual allowlisted tools execute; no LLM provider or GPU is invoked.

This is a new hypothesis on new episodes from the same public synthetic task family, not independent scientific-discovery validation. Dataset claims prevent replay within the durable research ledger; the operator can replace that ledger, so it is not sealed custody. Any recommendation remains for review only.

## Results

The frozen experiment completed **232 trials / 5,800 actual tool executions**, two generations, and stopped at the no-progress limit. All six new discount candidates were evaluated. No candidate passed every gate; the existing policy was retained. [Complete execution evidence](evidence/discount-research-v3.json).

| Final holdout arm | Frozen probe accuracy | Online-prefix accuracy |
| --- | --- | --- |
| Selected (unchanged baseline) |148/200 (74%)|608/800 (76%)|
| Current baseline |148/200 (74%)|608/800 (76%)|
| Fixed lower-only |110/200 (55%)|388/800 (48.5%)|
| Fixed trim-and-lower |90/200 (45%)|412/800 (51.5%)|

Because selected and baseline configurations are identical, they reuse the same trial results. Their zero paired difference and zero-width descriptive confidence interval are tautological, not independent evidence of equivalence. Prefix outcomes include learning and are reported separately from frozen probes. No discounted candidate was evaluated on this final holdout after failing the selection gates.

The half-life 1 candidates increased validation recurrent probes from 3/10 to 7/10 (overall 27/40 to 31/40), while training probes decreased from 30/40 to 29/40. Both were rejected for training regression. Half-lives 3 and 10 performed worse on recurrent validation. This is a lead for future preregistered research, not justification to relax the gate after seeing results. The default remains unchanged.

Wall time 136.429 seconds on Python 3.10.0, macOS 26.5.2 x86_64, with concurrent regression tests. No comparative latency, GPU, monetary-cost, model-weight or real scientific-discovery improvement is established. The changed SQL reduces query amplification, but large-history performance remains unmeasured. No deployment, live clinical integration, real inference-model test or Galahad restoration was performed.

Full regression: **1,129 tests passed, zero failures/errors, 65.207 seconds**, including 15 newly added tests. The initial restricted run reported 36 failures and 8 errors in environment-dependent sandbox/process/local-server tests; the authorized rerun passed the complete suite without code changes. [Validation metadata](evidence/discount-research-v3-validation.json). Evidence source hashes, execution counts and frozen-probe invariants were independently checked against final files.

## Review and performance boundaries

Independent review caught and resolved wrong-arm evidence acceptance: v3 checks exact returned policy fields against the requested configuration as well as numeric outcome counts. Review also replaced per-sample SQL age counts with one scoped window query per candidate. The SQL computes observation ages before filtering to the candidate and its recent window. It returns at most 100 samples per candidate, with at most 20 candidates. Same-context history may still require scanning/sorting in SQLite; large-history latency has not been measured. Query reduction is established by code inspection, not a measured end-to-end speedup.

Independent targeted validation passed 69 tests and then 15 discount-specific tests on final files. These are overlapping suites, not 84 distinct new tests. No agent ran real holdout data before the coordinator froze the experiment. Existing v2 behavior remains covered by regression tests.

## Reproduction and files

```sh
.venv/bin/python scripts/verify_galahad.py baseline
PYTHONPATH=src .venv/bin/python scripts/run_discount_research.py --database /tmp/nerve-discount-reproduction.sqlite --run-id discount-reproduction-v3 --output /tmp/nerve-discount-reproduction.json
git diff --check
```

Use unused paths. Reproducing this published dataset does not create a fresh confirmatory holdout. Interrupted experiments retain their consumed dataset claim. The CLI refuses output overwrite and can leave an empty reserved report on failure; inspect the SQLite run/cycle records.

Core changes are in `adaptive_memory.py`, `memory_gateway/learning.py` and `automation.py`. `discount_research.py` and `scripts/run_discount_research.py` use the shared durable `policy_research_loop.py` coordinator and actual `self_study.py` tool executor. New tests live in `test_discounted_memory.py` and `test_discount_research.py`; CPU/security verification groups include both.
