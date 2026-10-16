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

For a real domain, implement the `Domain` contract (`bank`, `predict`, `correct`,
`stream`, `skills`, `reward_source`) using trusted, versioned reward receipts.
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
changing the protected `tests/suite_tiers.json`. The dedicated six-test SDK suite
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
