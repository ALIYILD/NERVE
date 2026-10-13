# Forecast-based gain selection candidate

The previous diagnosis found that learning helped conditional forecasts under
drift but hurt them under stationary dynamics. This candidate separates shadow
learning from the gain used to plan commands. It reuses the single-use standard
EMA and inherited controller, filtering and signed recovery machinery.

The selection rule starts with the configured nominal gain. For each issued
nonzero action, nominal and shadow models make paired forecasts from the same
state estimate before the next observation is available. Each accepted velocity
observation resolves its stored forecast pair once. Learned gain becomes eligible
only when the last four resolved nonzero-action pairs all have strictly lower
absolute sensor error for the learned forecast. Selection affects future commands.

Four is a fixed exploratory design choice, not an optimized or calibrated
confidence level. Sensor noise, serial dependence and repeated decisions can
produce false switches; delayed or sparse evidence can postpone adaptation.
There is no guarantee of zero learning cost versus an exactly correct prior.

The development comparison uses frozen, ungated single-use and selected gain
with nominal, lower, higher and changing plant gains. All nominal priors stay
0.27; plant parameters are used only by simulation and offline scoring. Existing
outcome gates remain unchanged. No new heldout streams or default promotion are
authorized by this candidate implementation.

## Integration and boundaries

`PrequentialGainRuntime` is opt-in. Its controller stores paired forecasts for
issued simulated commands, uses bounded pending storage (default 128), expires
forecasts/scores by global step age (default 128), and retains only four resolved
scores. These are arrival/resolution order, not chronological re-fitting.

Parent ingestion validates and assimilates the observation first. Scoring then
uses only the immutable forecasts recorded before that observation, even though
the shadow EMA may already have updated. It never recalculates a historical
forecast with the updated model. Selection is restored after parent ingestion so
the existing learning hook cannot bypass the gate by writing `core.gain`.

Only authorized signed recovery clears the selector window/pending forecasts and
returns selection to nominal. It retains shadow gain and resets the inherited
local consumed-transition namespace. Filter propagation is unchanged. Pending
limits bound this new selector, not every inherited runtime history. A simulated
issued command is treated as executed by this harness; this is not the separate
authenticated physical execution-report interface.

## Recorded development result

Twelve seed-9 cases executed 960 simulated steps. All had zero defined violations,
15 externally supervised steps and one authorized recovery. The screen returned
`retain_baselines_and_diagnose`.

| Plant | Arm | Goal MAE | Prediction MAE |
|---|---|---:|---:|
| Nominal | Frozen | 0.143761226 | 0.006637115 |
| Nominal | Single-use | 0.141335585 | 0.006863716 |
| Nominal | Selector | 0.143761226 | 0.006637115 |
| Lower | Frozen | 0.166322817 | 0.017500831 |
| Lower | Single-use | 0.162749235 | 0.014292277 |
| Lower | Selector | 0.166322817 | 0.017500831 |
| Higher | Frozen | 0.291746054 | 0.086050138 |
| Higher | Single-use | 0.291746054 | 0.059016569 |
| Higher | Selector | 0.288332786 | 0.064494892 |
| Drift | Frozen | 0.160138309 | 0.023441317 |
| Drift | Single-use | 0.160138309 | 0.022385495 |
| Drift | Selector | 0.160138309 | 0.023441317 |

The selector passed the frozen comparison, but each plant failed at least one
criterion against single-use learning. The gate did not relax those comparisons.
Learned mode was used for 0/12/50/0 actual controller commands in
nominal/lower/higher/drift respectively; only the higher case had nonzero actions
in learned mode (22). Snapshot counts during external supervision are not counted
as controller commands. In lower dynamics, selection arrived during zero actions;
in drift it never became eligible. These observations motivate timing/coverage
analysis, not an unregistered relaxation of the four-win rule.

The nominal/drift frozen and single-use trajectories match the earlier saved
standard-learning comparison exactly. Seed 9 is reused development data. No
independent population gain, deployed improvement or neural training is claimed.

## Evidence and reproduction

The [full receipt](evidence/prequential-gain-development-v1.json.gz) contains all
traces and independent shadow-learning/selector audits. Its uncompressed SHA-256
is `b629857c762c141b9ed53751db0bccadb068297530b8fc2a09cda515d356fbb3`.
The [summary](evidence/prequential-gain-development-summary.json) records the
fixed comparisons and actual learned-mode command counts. Independent review
verified all 24 source pins and recomputed the screen without rerunning episodes.

```sh
PYTHONPATH=src .venv/bin/python scripts/demo_prequential_gain.py --output /private/tmp/nerve-prequential-gain-reproduction.json
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_prequential_gain*.py' -v
.venv/bin/python scripts/verify_galahad.py baseline --timeout-seconds 600
```

Use a fresh output filename. The development driver is bounded to 30 seconds per
case and 360 seconds overall; this is local CPU simulation, not a GPU or inference
benchmark. Unit/development tests cover immutable forecasts, ties, mixed windows,
late and corrected observations, quotas, expiry, recovery authorization, receipt
tampering and baseline equivalence. Full regression passed **1,703 tests in 132.319 seconds**, including 19 new tests,
with zero failures or errors. See the [validation receipt](evidence/prequential-gain-development-validation.json).
