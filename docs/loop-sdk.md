# Loop SDK: synthetic development contracts

`PYTHONPATH=src python3.13 -m nerve_awim.loop demo --domain perfflux-sandbox --budget 100`
runs learn → propose → evaluate → adapt using the existing `GoalOrchestrator`, then
writes `bundle.json` and a SHA256 manifest under `receipts/loop-demo-*`.
Use `python -m nerve_awim.loop replay PATH` in a fresh process to independently
recompute the complete bundle with zero model calls. Scientific and
`clinicalos-sandbox` use the same API. Python >=3.12 is required by the package.

```python
from nerve_awim.loop import Loop
loop = Loop('perfflux-sandbox', '/private/tmp/my-loop')
loop.learn(recorded_episodes)
candidate = loop.propose()
receipt = loop.evaluate(candidate, loop.domain.bank(100), gate='dev')
trace = loop.adapt(loop.domain.stream())
print(loop.status())
loop.close()
```

`learn` accepts recorded IDs, failure clusters, boolean outcomes and source receipt
hashes, without inference. These references are assertions from a trusted host,
not signatures. It writes the append-only `ExperienceStudyStoreV2` companion
schema; it does not mutate the original, protected four-ordinal format-probe v2.
`propose` counts failures from that store and registers one typed prompt-fragment
candidate. The current sandbox generator has one repair template; it does not
claim three autonomous novel proposals per scientific family. Reverted seams are
excluded by failure cluster. `evaluate` registers the exact candidate, bank hash,
controls and keep rule before running deterministic checks. Always-abstain and
seeded random are actually scored per item. Keep requires net wins >=6, losses
<=1, no safety errors and strictly greater total accuracy than both controls.
A kept dev candidate never becomes a routed incumbent or a signed skill.

`adapt` consumes recorded paired boolean rewards. A two-sided CUSUM monitors
correctness, discordance and abstention. A rolling full-information router scores
only the two host-declared sandbox retained skills, verifies switches for ten
items and rolls back after three consecutive served failures. It is not a
production bandit: both counterfactual rewards must be available. Monitor and
router state are committed atomically with each unique stream receipt in SQLite
WAL with FULL durability. Resume rejects changed stream/configuration hashes and
skips committed items. It makes zero external calls, so this demonstrates no
repeated inference only for recorded/synthetic outcomes; exactly-once remote
inference across a crash requires a provider idempotency protocol.

All three banks are deliberately small synthetic contracts. The scientific demo
does not replay the signed scientific banks or establish canonical D5. PerfFlux
labels represent direct/cached-batch choices; Clinical OS labels represent title/
abstract retrieval over synthetic metadata. No real workloads, patient data,
clinical benefit, latency improvement or performance deployment is claimed.
The injected degradation affects served outcomes, not retention or installation.

For a real domain, add a reviewed, versioned source adapter implementing `bank`,
`public_input`, `predict`, `correct`, `stream`, `skills` and `reward_source`, using
trusted reward receipts. The current release accepts only the three built-in
contracts; arbitrary custom `Domain` objects cannot be injected at runtime.
A real reward importer must independently verify and scope the source before
`learn`, and supply paired outcomes or a separately registered exploration
policy for adaptation. Loop 38 clinician sign-off and PerfFlux workload data are
external inputs still required. The SDK has no clinician approval implementation.
`gate='signed'` fails closed; host code must call the existing signed gate outside
the SDK, keep sealed outputs private and queue the full-form human signing
payload. No SDK method signs, installs, retains or edits registry/trust.

The PCCP-style mapping in `NERVE_EXTERNAL_METHODS_ADOPTION.md` is implemented here
only as bounded change specification (typed seam), predeclared assessment
(controls/keep rule), monitoring (CUSUM), traceable receipts and rollback. It does
not establish regulatory compliance or authorize a medical change.

Dedicated tests: `PYTHONPATH=src python3.13 -m unittest discover -s tests -p
 test_loop_sdk.py`. The existing fast runner discovers all test modules absent from
`slow_modules`, so these SDK tests automatically belong to the fast tier without
changing the protected `tests/suite_tiers.json`. The original dedicated eight-test SDK suite
passed; W0 reported that the full fast tier exceeded its existing 180-second
deadline. Full fast-tier completion is therefore unverified, not blocked by a
missing SDK integration.

Monitoring uses a fixed retained reference skill's correctness, so successful
routing does not itself change the detector's baseline. Failed served skill
variants are quarantined for 60 items; a detected shift cannot immediately clear
that quarantine. Canary failures and disagreements between a served variant and
its paired retained reference trigger rollback. Normal sustained workload changes
are handled by rolling scores. This assumes trusted paired reference outcomes.
The registered three-shift synthetic stream is an engineering fixture, not a
power-calibrated statistical drift benchmark; initial local fixture iterations
were used to correct routing/monitor interaction before the final receipt run.

Learning ingestion uses one authority: the append-only study-v2 companion. There
is no separately committed SDK episode table. Each call of up to 10,000 records
is validated and appended in one transaction, so a conflict anywhere in a batch
leaves the complete batch unapplied. Reordered identical records are idempotent.
Episode identity is domain + caller ID; changed content for an existing ID fails
closed. `source_ordinal` is the explicit position in a multi-row source receipt;
it defaults to 0 for a single-record receipt and never derives from batch order.
The demo supplies every baseline item's original ordinal. Proposals derive their
evidence hash and failure clusters from this same authoritative store.

The earlier dual-store development implementation was not atomic. Its local
checkpoint directories are rejected with an explicit migration/fresh-directory
error; no silent migration or deletion occurs. Arbitrary external episode sinks
are rejected because the SDK cannot atomically commit their side effects. SDK
bundles committed after the correction were regenerated and independently
replayed against the corrected source pins.

D7 is partial for the originally requested `evaluate(..., gate='signed')`
capability: this release exposes the mode but refuses it safely. The external
signed-gate handoff is a documented boundary, not an implemented SDK signed
assessment path.

## Synthetic contract v2 (continuation)

New demos use `loop-demo-v2`. Predictors receive an allowlisted copy containing
only item ID and public `task`; evaluator truth, safety strata and cluster labels
are withheld. Label-mutation tests hold inputs fixed and flip private rewards:
predictions stay identical while evaluation changes. This is input separation,
not process isolation against malicious Python code.

The scientific task extracts the sign of a reported delta. PerfFlux compares
explicit synthetic direct latency against batch overhead plus cache misses.
Clinical OS matches a query term against synthetic title/abstract metadata;
this is retrieval relevance, never clinical correctness. The incumbent abstains
when its summary is unavailable; the candidate uses observable structured context.
These hand-written deterministic repairs exercise the SDK contract, not autonomous
scientific discovery or measured production performance. No model calls occur.

`protocol.json` registers version, bank, source hashes, budget and the unchanged
keep rule before even baseline predictions. Evaluation separately registers the
candidate and bank before scoring. Fresh-process replay first verifies the exact
source pins and protocol, then recomputes the receipt. Existing v1 receipts remain
unchanged and require their original pinned checkout; v2 refuses to silently
reinterpret them. Hashes establish consistency, not authenticity or independent
reward validity. `learn` continues to accept host-asserted receipt references.

Adaptation still consumes the existing deliberately injected paired-reward
fixture. It is not derived from these task banks, and does not substantiate D5
or production counterfactual reward availability. Signed evaluation remains
fail-closed. This version improves task/reward separation only; the generator
still has a single context repair and does not satisfy D1's three proposals.

Direct `evaluate` registrations also pin the SDK evaluator and domain source
hashes. Runtime custom domain subclasses/configurations are rejected until a
reviewed, versioned contract is added to the domain registry in source (not the
protected skill registry). This avoids pretending unpinned host code is a fixed
evaluator. Real-domain integration currently requires that source-level adapter.

Continuation validation: all 13 SDK tests passed and all three v2 bundles replayed
in separate fresh processes under the shared test lock. See
`docs/galahad/140-sdk-task-reward-separation-20261017.md` and
`receipts/sdk-v2-validation-20261017.txt`; inherited SQLite ResourceWarnings remain.
