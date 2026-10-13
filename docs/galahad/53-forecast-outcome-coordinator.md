# Forecast findings in restartable research memory

This cycle connects the completed forecast study and recorded online integration
evidence to NERVE's existing verified memory. It adds a versioned path for positive
forecast findings while preserving the source-pinned rejection workflows.

The coordinator adopts completed evidence, proposes a scoped episodic research
fact, waits for separate trusted fact review, and emits a forecast-only review
packet. It must not execute the study or development simulator on adoption or
resume. An approved fact is evidence for subsequent research planning; it is not
permission to change control policy, authorize recovery, deploy, or reuse a
consumed holdout.

## Evidence boundary

The study validator checks all frozen stages, claims and source provenance.
Recorded online trajectories are checked for arithmetic correctness; their
forecasts and metrics are recomputed from permitted sensor/action inputs. The
online artifact's digest and source hashes bind the recorded implementation.
The importer does not infer independent proof of missing comparison states from
the demo's comparison booleans. The fact states the narrow verified conclusion:
synthetic forecast improvement plus validated recorded forecast/replay equivalence.

Memory proposals are pending until a distinct host-issued review capability
approves the factual receipt. Approval gives no utility reward. Existing tenant,
agent, context, revocation, expiry and content-integrity checks remain authoritative.
Durable receipt claims prevent duplication and resurrection after deletion.

Independent review found that hashing the entire auxiliary online artifact into
claim identity allowed unverified state details to create duplicate study claims.
The fix derives identity from the canonical verified study plus the fixed bridge
protocol. Auxiliary online evidence remains bound in fact provenance, but changing
it cannot create a new claim or bypass a deletion tombstone.

## Lifecycle boundary

The run journal binds scope, source hashes, evidence locations and receipt identity.
Restart revalidates evidence and memory status. It must never blindly retry failed
work or accept changed artifacts under an old completed claim. Missing, revoked,
expired or rejected facts cannot authorize a downstream review packet.

Local synthetic capabilities demonstrate process boundaries; they are not a
production identity provider or clinical authorization system. No model weights,
clinical decisions, real Galahad restoration or production deployments are changed.

## Validation in this cycle

Full regression passed 1,619 tests in 220.411 seconds with zero failures or errors.
Independent review passed all 32 new bridge/coordinator tests. These include an
actual fresh subprocess resume with fixture evidence, crash reconciliation,
source/artifact changes, pending/rejected/expired/revoked facts, wrong evaluator,
cross-scope access and deletion tombstones. Unit fixtures mock expensive upstream
study verification where needed; the actual evidence-adoption run separately
executes the full existing study validator.

The initial actual invocation created one pending fact, and an authoritative
scoped query returned zero approved records. Independent read-only inspection
confirmed one matching durable receipt claim and no completed packet at that stage.

A separate actual process then reviewed the fact and emitted the packet with
status `forecast_only_review_required`. Scoped retrieval returned exactly one
approved record with evaluator `verified-forecast-receipt-v1` and a null outcome
score. A cross-tenant query was denied. The coordinator executed zero new research
episodes and left promotion and control-policy-change authorization false.

Memory ID: `47d28437514a4d1d98d33dbb1a852ddf`. Stable study-fact receipt:
`44848a5c38164bfb27d7ef7d896c7a4fb3eec7ccf2554cb2b9f2b56cfba1ef79`.
The [full packet](evidence/forecast-research-coordinator-v1.json.gz) includes scope,
source hashes and evidence paths; the [summary](evidence/forecast-research-coordinator-summary.json)
contains the exact approved fact. Packet SHA-256:
`0649c7c1e2f82c1373bab6f420852d15a2d637290f5351d35effef508c1d3a66`.
Environment: Python 3.10.0, macOS 26.5.2 x86-64, CPU only.

The subsequent fresh-process resume exited successfully. Packet bytes and
modification time were unchanged, the memory database still contained exactly one
record, and the original study report, study ledger, shared study claims and raw
online demo retained their hashes and modification times. Independent inspection
matched all 67 source hashes and reconciled the approved record, claim and journal.
See [resume evidence](evidence/forecast-research-resume-v1.json) and
[validation results](evidence/forecast-research-validation.json).

## Reproduction

From the repository root, run the following command to propose or resume the
synthetic fact. It validates the existing evidence chain and never starts a plant
episode. All predecessor paths must contain the recorded earlier cycle artifacts.

```sh
PYTHONPATH=src .venv/bin/python scripts/run_forecast_research_coordinator.py \
  --memory /private/tmp/nerve-forecast-research-memory-v1.sqlite \
  --directory /private/tmp/nerve-forecast-research-coordinator-v1 \
  --journal /private/tmp/nerve-forecast-research-claims-v1.sqlite \
  --study /private/tmp/nerve-phase-forecast-study-v1 \
  --claims /private/tmp/nerve-phase-forecast-study-claims.sqlite \
  --predecessor /private/tmp/nerve-observer-reanalysis-v1.json \
  --source-study /private/tmp/nerve-evidence-gated-study-v1 \
  --source-claims /private/tmp/nerve-evidence-gated-study-claims.sqlite \
  --coordinator-directory /private/tmp/nerve-memory-research-v1 \
  --coordinator-journal /private/tmp/nerve-memory-research-claims.sqlite \
  --online-artifact docs/galahad/evidence/online-forecast-demo-v1.json.gz \
  --online-summary docs/galahad/evidence/online-forecast-demo-summary.json
```

On the first invocation the result is `waiting_for_fact_review`. For this local
synthetic fixture only, add `--review-fact` to the same command to invoke a separate
host-issued read/approve capability. This validates the receipt again and approves
the historical fact; it is not clinical or candidate-promotion approval. Repeating
the original command in a fresh process revalidates the completed packet without
changing its bytes or repeating experiments.

```sh
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_forecast_outcome_memory.py' -v
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_forecast_research_coordinator.py' -v
.venv/bin/python scripts/verify_galahad.py baseline
```
