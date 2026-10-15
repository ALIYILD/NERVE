# Restartable prequential research loop

The latest development experiment rejected a forecast-based gain selector. This
loop connects its verified result to automatic timing diagnosis and durable
completion, so restarting the research process does not rerun consumed cases.

The fixed graph adopts the recorded twelve-case experiment, validates its source
pins, physical traces, shadow learning, immutable forecasts and comparison gates,
then diagnoses why selection did or did not become eligible. No agent-generated
code or arbitrary command executor is introduced. A rejection retains baselines
and terminates with a new-hypothesis requirement; restarting cannot turn rejection
into promotion or silently repeat an experiment.

The timing analysis distinguishes learned-mode snapshots from actual controller
commands and nonzero actions. Eligibility during external supervision or zero
commands is not counted as a useful control action. Recorded phase boundaries
are offline diagnostic labels, never information supplied to the selector.

## Recorded timing evidence

| Plant | First full window | Forecast wins / ties / losses | Eligible steps | Eligible controller commands | Eligible nonzero commands |
|---|---:|---:|---:|---:|---:|
| Nominal | 8 | 3 / 2 / 9 | 0 | 0 | 0 |
| Lower | 4 | 8 / 2 / 0 | 27 | 12 | 0 |
| Higher | 4 | 22 / 2 / 0 | 65 | 50 | 22 |
| Drift | 8 | 4 / 2 / 7 | 0 | 0 | 0 |

Lower-gain eligibility covered steps [29,55) and [79,80); higher-gain eligibility
covered [11,55) and [59,80). Authorized recovery at step 55 cleared old selection
evidence. Eligibility includes externally supervised steps where the selector
cannot issue control. These counts describe the reused seed-9 trajectories;
they are not estimates of general switching reliability.

## Durable execution

The coordinator reuses the existing supervisor's exclusive lock and adds a
source-bound SQLite journal. It claims the canonical input before diagnosis,
binds run paths and source hashes, publishes a report atomically with fsync, and
records the completed digest. Failures remain consumed. A changed configuration,
missing output or corrupted completed report cannot silently restart work.

Resume recomputes read-only validation/diagnosis and compares the existing report;
it does not run plant episodes or rewrite the report. The receipt binds 28 source
files. This is trusted local research orchestration, not network authentication,
model-weight learning or clinical deployment.

The actual run used `/private/tmp/nerve-prequential-research-v1` and shared journal
`/private/tmp/nerve-prequential-research-claims-v1.sqlite`. It completed two nodes:
receipt adoption and timing diagnosis. A fresh process resumed successfully with
one completed journal entry. Both the report and input retained identical bytes
and modification times. The report SHA-256 is
`9845819604bca35908fec2f04f1cb4758a5a47aab0f3e4cf08255bc4feda0cb3`.
Independent review rechecked all pins, the journal and the exact diagnostic.

See the [full coordinator receipt](evidence/prequential-research-v1.json.gz),
[summary](evidence/prequential-research-summary.json), and
[fresh-process resume evidence](evidence/prequential-research-resume.json).

## Independent reproduction

Choose a fresh directory and shared journal for an independent reproduction.
Repeat the same command to check resume; keep its directory/journal/input binding.

```sh
PYTHONPATH=src .venv/bin/python scripts/run_prequential_research.py --directory /private/tmp/nerve-prequential-research-reproduction --journal /private/tmp/nerve-prequential-research-reproduction.sqlite --artifact docs/galahad/evidence/prequential-gain-development-v1.json.gz
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_prequential_timing_diagnostic.py' -v
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_prequential_research_coordinator.py' -v
.venv/bin/python scripts/verify_galahad.py baseline --timeout-seconds 600
```

Twenty-two focused tests and independent review passed. The actual coordinator
executed zero new episodes and used no heldout outcomes. Its terminal status is
`new_registered_hypothesis_required`; the full self-improvement goal remains
unachieved. Subsequent work needs a distinct evidence-backed hypothesis rather
than a blind replay or a relaxed acceptance threshold.

Full regression passed **1,725 tests in 135.081 seconds**, with zero failures or
errors. See the [validation receipt](evidence/prequential-research-validation.json).
