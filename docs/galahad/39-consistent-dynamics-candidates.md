# Opt-in dynamics and planning candidates

The objective-mismatch diagnosis led to two executable research candidates in `src/nerve_awim/consistent_dynamics.py`. Existing controller modules remain unchanged, preserving the source pins and baseline behavior of earlier studies. Nothing is promoted into the default runtime.

`ConsistentDynamicsRuntime` constructs the existing identity-bound recovery chain with two independent experimental controls:

- `consistent_filter=True`: after successful sensor ingestion, the filter uses the current learned gain for its next transition. Each executed filter action records its gain in an immutable tuple; delayed observation replay uses those historical coefficients. Learning does not rewrite prior propagation. Authorized recovery installs an empty-history filter from the accepted recovery observation and retained learned gain.
- `planning_horizon=1..5`: horizon 1 delegates directly to existing selection. Longer horizons enumerate at most 243 discrete sequences, score cumulative target/action/risk cost, and check the position and velocity envelopes at every step. Ties use deterministic lexicographic sequence order. An infeasible sequence set raises; it does not manufacture a safe zero action.

The longer-horizon branch first calls the full inherited selection chain, preserving phase, freshness, incident and first-step feasibility checks. Recovery still requires the existing identity verification, signed approval, evidence and nonce ledger. No model output authorizes recovery.

The empirical radius remains fixed across projected steps. This is an explicitly heuristic envelope test, not a calibrated multi-step uncertainty bound or physical-safety proof. The intended prospective experiment uses the drift estimator, which deduplicates sensor-pair learning; the existing standard estimator's repeated-pair behavior is unchanged.

## Mechanism evidence

Tests exercise constant-gain equivalence with the original filter, delayed nonzero observation correction against independent arithmetic, prospective-only gain changes, immutable history, invalid-input rejection, learned-gain propagation, recovery reseeding, signature/identity bypass denial, freshness expiration, bounded horizon validation, later-step infeasibility and radius gating.

A concrete planning fixture (`position=0`, `velocity=1`, `target=1.2`, `safe_position=1`) selects action `0` at horizon 1 and `−1` at horizon 3. Another fixture admits a first step but rejects every longer sequence. These verify that the new depth changes actual decisions while preserving rejection behavior.

Development smoke seed **3**, drift regime, exercises all four filter-consistency × planning-depth combinations with real controller execution and synthetic host identity. Every combination completes the existing trace validator and supervised recovery without a recorded envelope violation on that one fixture. The disabled-consistency/horizon-1 control is exactly equal to the original episode output. These are implementation checks, not representative performance results. No prospective validation or holdout streams were consumed, and no general performance gain is claimed.

## Reproduce

```sh
cd /Users/aliyildirim/nerve-galahad
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_consistent_dynamics.py -v
.venv/bin/python scripts/verify_galahad.py baseline
```

The next required step is a registered factorial study on fresh development/validation streams, followed by a sealed final test only after selection and unchanged correctness gates. The study must retain both the frozen-gain control and the existing adaptive controller, distinguish filter consistency from planning depth, account for additional planning work, and allow a no-improvement outcome. The diagnostic followup's next-study request is not yet wired to execute this candidate study automatically.

Final verification: **1,375 repository tests passed in 85.149 seconds** with zero failures/errors. Independent review reran all 10 candidate tests and found no blocking defects. The prior recovery-study and diagnostic receipts still validate against current source pins. [Validation record](evidence/consistent-dynamics-validation.json).
