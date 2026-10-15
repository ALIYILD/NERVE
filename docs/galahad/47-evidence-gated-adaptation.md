# Evidence-gated adaptation candidate

This development cycle checked what the previous prediction metric measures and
implemented an opt-in gain-learning candidate. No default controller changed and
no candidate was promoted. The candidate still requires prospective matched
training/validation and independent final evaluation before any improvement claim.

## Exact error audit

`scripts/audit_prediction_errors.py` validates the saved study receipt before
analyzing training traces. For every recorded step it reconstructs:

```
predicted_velocity - true_velocity
  = .82 * (estimated_velocity - previous_true_velocity)
    + (estimated_gain - true_gain) * actual_action
```

The actual 128 training episodes/10,240 steps gave a maximum identity residual of
`1.1102230246251565e-16`. The actual action includes the harness's explicitly
recorded external-supervisor action zero. Its gain term is consequently zero;
its forecast error comes entirely from the state term. During unavailable periods
the controller's filter remains frozen until authorized recovery. Correcting this
requires explicit host-owned actual-action observation, not pretending zero is an
authorized autonomous action. A future observer comparison needs identical
observer capabilities on both frozen and adaptive controls.

That outage effect does not explain every failed gate. Across eight stationary
training seeds, retain-window horizon-1 had controller-only prediction MAE
0.005693238 versus frozen horizon-1 0.005110622. Their external-supervisor MAEs were
0.031831372 and 0.032248827 respectively. In drift, retain-window horizon-1 had
controller prediction MAE 0.028357882 versus adaptive-consistent horizon-1
0.025002302. Both absolute state and gain terms were larger for the candidate.
Component signs can cancel; absolute components are not additive causal effects.
The audit uses true state only for retrospective scoring, never model input.
[Full audit](evidence/prediction-error-audit-v1.json).

## Candidate behavior

`EvidenceGatedGain` reuses timestamp validation, finite observation-window storage
and transition deduplication from `EvidenceWindowGain`. It consumes only adjacent
sensor velocity/action evidence through the existing controller fitting hook.
Evidence consumption and actual parameter change are distinct: `processed` tracks
accepted transitions, while `gain_changes` counts changes to the estimate.

Fixed development defaults are a four-observation window, four required samples,
standard-error multiplier 3 and minimum shift 0.03. After accepting evidence, the
candidate retains its current gain unless:

```
abs(sample_mean - current_gain) > 0.03 + 3 * sample_standard_error
```

An accepted change uses the sample mean clipped to the existing [0.01, 1] model
range. The threshold is a noise-resistance heuristic, not a calibrated confidence
interval, sequential hypothesis test or guarantee against false changes.
Correlated sensor differences, repeated checking and delayed observations limit
statistical interpretations. No parameter search was performed in this cycle.

`EvidenceGatedRecovery` retains the existing signed recovery boundary, sensor
freshness guards, historical transition gains and bounded planner. Authorized
recovery may forget the observation window while retaining the gain, or retain
and reindex observations using the existing policy. Forgetting requires four new
observations before another change. `prior_weight` is rejected because it is not
an effective parameter of this gated estimator. Existing defaults are unchanged.

## Development evidence

Eleven unit/integration tests cover insufficient evidence, stationary/noisy gain
retention, consistent shifts, high-variance inhibition, clipping, duplicate/invalid
observations, timestamp ordering, strict configuration, recovery authorization,
forgetting and historical filter consistency. Five audit tests cover arithmetic
cancellation, receipt failures/changes and exclusion of held-out payloads.

Two development smoke episodes used seed 2, outside registered study splits.
Both passed the existing real trace validator, recorded zero envelope violations,
67 controller steps, 13 external-supervisor steps and one authorized recovery.
The stationary episode consumed 11 observations and retained gain 0.27. The drift
episode consumed eight and ended at gain 0.4868017144538862. This is executable
behavior evidence, not a paired performance comparison or successful adaptation
across all regimes. No prospective evaluation or holdout streams were consumed.

## Reproduction

```sh
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_evidence_gated_dynamics.py -v
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_prediction_error_audit.py -v
PYTHONPATH=src .venv/bin/python scripts/audit_prediction_errors.py \
  --study /private/tmp/nerve-evidence-window-study-v1 \
  --claims /private/tmp/nerve-evidence-window-study-claims.sqlite \
  --supervisor /private/tmp/nerve-research-supervisor-v1
.venv/bin/python scripts/verify_galahad.py baseline
```

Smoke reproduction (development only):

```python
from unittest.mock import patch
from nerve_awim.evidence_gated_dynamics import EvidenceGatedRuntime
from nerve_awim.memory_gateway import recovery_adaptation as worker
for scenario in ('stationary', 'drift'):
    with patch.object(worker, 'NerveResearchRuntime', EvidenceGatedRuntime):
        row = worker.episode(2, scenario, True)
    worker.validate(row, 2, scenario, True)
    print(scenario, row['metrics'], row['final_gain'])
```

The temporary binding is process-local development wiring; the future registered
worker must explicitly audit the new estimator's gate decisions and provenance.
No hardware/Galahad restore, neural-weight training or clinical deployment has
been validated by this work.

Full regression: **1,491 tests passed in 133.604 seconds**, zero failures/errors.
[Validation record](evidence/evidence-gated-validation.json).
