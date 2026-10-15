# Observation-evidence gain candidate

The identification diagnostic found sparse fitting updates and inaccurate retained gains around the blackout. `evidence_window_dynamics.py` provides an opt-in hypothesis for a fresh comparison: moderate noisy updates with a bounded observation window, and optionally discard old fitting evidence after authorized recovery. Existing estimator/controller sources and all earlier receipt pins remain unchanged.

## Learning rule

Only consecutive timestamped velocity observations associated with a recorded nonzero action can generate a sample. The existing core supplies those pairs. Samples use `(velocity - retention * previous_velocity) / action`, retaining the established eligibility interval [−0.3, 1.3]. Boolean/nonfinite inputs, invalid times, zero actions and duplicate timestamps cannot update the estimator.

The candidate keeps the newest 16 eligible transition timestamps by default, not the latest 16 arrival events. Delayed observations older than an already full window are rejected without mutation. Its gain is:

`clip((prior_weight * initial_gain + sum(window_samples)) / (prior_weight + sample_count), 0.01, 1.0)`

The fixed prior weight defaults to 4. The candidate's window and prior define adaptation; the inherited drift hook is enabled with the fixed compatibility value `learning_rate=0.08`, not used as an EMA rate. Other inherited rate values are rejected to avoid implying they tune this learning rule. The reported variance is the mean squared sample deviation about the un-clipped regularized mean; the prior is not included as a variance sample. This is a heuristic regularizer, not calibrated Bayesian uncertainty. `drift_count` counts eligible innovations exceeding 0.12 against the previous gain, not verified regime changes.

The observation deque is bounded (configurable 1–64). The deduplication set retains all consumed transition IDs in the current bounded episode epoch and is cleared by the existing recovery reseed. This is not an unbounded-lifetime storage guarantee.

## Recovery modes

Both modes retain gain until new fitting evidence arrives and inherit identity, signed approval, freshness, evidence and replay gates.

- **Forget window:** successful authorized reseeding clears fitting samples and resets the variance proxy. The next genuine sample is combined with the original prior; gain may jump toward that prior. No smooth-continuation guarantee is made.
- **Retain window:** existing fitting samples remain older than new-epoch observations. Their local ordering indexes are renumbered negative after the epoch boundary, while inherited transition dedup is cleared. New samples gradually replace older evidence.

Rejected approval and invalid reseeding leave estimator evidence untouched. Recovery observations still cannot become fabricated action/velocity fitting pairs. Filter propagation follows the resulting gain prospectively and preserves the coefficients used for historical actions.

## Development evidence and limits

Seven tests exercise exact arithmetic, negative actions, clipping, constructor/input rejection, timestamp ordering, eviction, duplicate suppression, missing-pair behavior, recovery retention/forgetting, approval denial and historical filter-gain preservation. A synthetic drift smoke test uses development seed **5** across retain/forget × horizons 1/3. All four runs exercise learning and supervised recovery, pass the original complete trace validator, and show no envelope violation on that fixture.

No training/validation/final-evaluation dataset was consumed for selection. These tests show implementation behavior, not improved accuracy, safety or general intelligence. The candidate is not enabled in the default runtime, and the research supervisor does not yet dispatch its prospective study. A future registration must compare it against the existing frozen and adaptive controls at matched planning depth, preserve independent streams and permit rejection.

```sh
cd /Users/aliyildirim/nerve-galahad
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_evidence_window_dynamics.py -v
.venv/bin/python scripts/verify_galahad.py baseline
```

Final verification: **1,412 repository tests passed in 237.141 seconds**, with zero failures/errors. Independent review reran all seven candidate tests under normal and optimized Python without blocking findings. All four previous supervisor graph receipts still validate unchanged. [Validation record](evidence/evidence-window-validation.json).
