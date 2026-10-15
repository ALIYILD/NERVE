# External methods: staged implementation

The user authorized implementation before the slice-2 verdict on 15 October 2026,
with real holdout execution and promotion disabled. The new implementation lives
in `src/nerve_awim/external_methods`; it does not edit the frozen v3 transport,
scorer, study or slice gate. Historical source pins remain authoritative.

## Implementation map

| Plan item | Implementation and status |
|---|---|
| 36.6 registration v2 | `contracts.register`: complete sections, pilot history, exploratory/confirmatory mode, input hashes and sampling/transport configuration; gate persists the registration before outcomes |
| 36.5 shuffled orders | `runner.ordered_tasks`: seeded stratified order; `robustness_verdict`: complete registered seed coverage, variance and sign reversal; real cross-order studies remain unrun |
| 36.7 five axes | `runner.evaluate` and `workflow.audit_v3`: accuracy with descriptive Wilson intervals, efficiency, robustness, safety, explicitly deferred clinician UX |
| 37.2 replay cache | `ResponseCache`: request identity includes model digest, full prompt, parameters and replicate; raw response and response hash; holdout manifests export only count and digest |
| 37.3 lesson | `Archive.retain`: optional bounded generator note; it never enters scoring |
| 39.3 archive | All verdicts retained with bank/model/incumbent identities; re-eligibility reports which identity changed |
| 39.4 diagnosis | `evaluator.diagnose`: evidence-derived labels independent of strict scoring |
| 39.5 seams | Closed data schemas, no executable patch/import path; durable proposal budget and regime/seam rotation in `RepairPlanner`; unknown regimes reported as walls |
| 40.2 sequential gate | Fixed-bet paired e-process, atomic wallet charge, fresh item allocation, all-control gates, per-stratum veto, plateau/futility/item-budget outcomes; synthetic/dev only |
| 40.3 capacity | Complete declarations and prices; measured snapshot mismatch veto and gain-adjusted threshold; historical v3 has no retroactively invented declaration |
| 40.4 verifier | Dimensional unit checks, source resolution/currentness/query match, value equals cited measurement, named abstention rule; violation veto |
| 41.2 evidence tiers | A/B/C requirement lists; all tiers require human signature; review status confers no deployment authority |
| 41.3 skills | Reviewed skill record and seam/regime library, preserving usage data and supersession |
| 42.4 evaluator | CLI launches a separate trusted worker with network/subprocess/write guards; candidates are closed data, not imported programs |
| 47 white-box | Hardware/toolkit/validation/retirement contracts and honest unavailable status; no validated probe, activation capture or live verifier integration claimed |
| PCCP | [Design alignment](pccp-mapping.md); advisor review outstanding |

`runner.evaluate` wires preregistration, task ordering, claims, response caching,
independent strict scoring/diagnosis/domain verification, the gate, retained
outcomes, repair proposals and five-axis reporting. Its trusted evaluator callback
must provide normalized outputs for candidate, deployed incumbent, always-abstain
and random controls, measured capacity, usage and latency. It cannot evaluate
holdout. The retrospective CLI decodes existing v3 responses without inference.

The outcome-release bridge is `scripts/reconcile_external_methods.py`. It pins
the new module and script hashes plus receipt/dev input hashes, delegates to the
worker and checks the no-model-call/no-holdout/no-promotion result. Its goal means
"retrospective audit complete", not "all adoption research complete".

## Statistical design and limits

With registered bet b in (0,1), a discordant win multiplies E by 1+b and a loss
by 1-b; ties multiply by 1. E starts at 1. Under the conditional null that a win
has probability at most one half among discordances, this is a nonnegative
supermartingale. The implementation stores log E and compares against log(1/alpha).
It requires that threshold against incumbent and both controls. Requiring every
control comparison to pass is an intersection-union test; it is not "pick the
best comparison". Reverse per-stratum tests use alpha/number-of-strata and latch
any veto. Final review still needs all other registered evidence requirements.

Alpha is charged once per unique immutable study registration; no refunds for
infrastructure failures or negative results. Total alpha is at most .05. The
200-study demonstration spends .00025 per proposal. A default .05 study would
consume the entire default wallet; a continuing program must register smaller
allocations. Item IDs cannot be reused within a bank across proposals.

Anytime validity does **not** license adaptive reuse of exposed finite holdout
items. The fresh-allocation requirement is intentional. A mathematically justified
reusable-holdout protocol is future work; the implementation does not claim that
the reserve can be reused indefinitely. A meaningful power analysis for the
100-item reserve remains required before live registration.

The simulation uses 200 proposals, exactly 40 harmful, with discordant win
probability .45 for harmful and .85 for beneficial proposals. Each gets 100 fresh
synthetic pairs, shared between comparators. Its naive comparator makes uncorrected
one-sided normal-test looks at n=20,40,60,80,100; the sequential comparator uses the
registered bet .5 and futility threshold .05. It reports failures honestly. This
is a NERVE simulation inspired by Lewis, **not an exact reproduction of his
experiment or of the historical NERVE slice acceptance rule**. A successful
simulation is neither a universal <1% guarantee nor evidence about clinical data.

## Persistence and isolation

The gate uses private-directory SQLite transactions, synchronous FULL, an HMAC
event chain and a transactional checkpoint. Every study revalidates the chain.
Cache invalidation uses SQLite connection changes and external data-version
changes. Altered events or deleted tail events fail closed. A host-held key must
not be available to the generator. Whole-database rollback with a matching old
checkpoint needs an external monotonic witness to detect; that is not supplied
by filesystem hashes. The synthetic demonstration key is explicitly public and
must never protect real evidence.

Claim precedes inference. A cached response is recovered and scored without
another call. A crash after dispatch but before durable response storage is
ambiguous: it returns `incomplete_infrastructure`, without retrying or claiming
exactly-once server execution. This unavoidable ambiguity is not silently treated
as a successful restart. Replayed completed results are byte-identical.

The evaluator process guards are defense in depth, not OS isolation from a
malicious same-user/root process. Real gate activation requires a reviewed
host-level isolation and signing adapter. No self-rewriting code, arbitrary
imports or generator-defined verifier exists in this module.

Capacity measurements are supplied by the trusted evaluator as complete candidate
snapshots; a real transport adapter must derive them from actual run usage rather
than copy declared values. The staged simulation uses zero-resource snapshots.
The retrospective v3 audit reports missing capacity and order studies explicitly.
It does not upgrade legacy evidence into a preregistered capacity-adjusted result.

## Commands

```sh
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_external_methods.py
PYTHONPATH=src .venv/bin/python scripts/run_external_methods.py status
PYTHONPATH=src .venv/bin/python scripts/run_external_methods.py simulate --output /private/tmp/nerve-methods-simulation
PYTHONPATH=src .venv/bin/python scripts/run_external_methods.py audit-v3 \
  --receipt docs/galahad/evidence/scientific-candidate-v3-study.json \
  --development /Users/aliyildirim/nerve-research-runs/task-bank-v1/dev.json \
  --output /private/tmp/nerve-methods-dev-audit
```

Use a new output location after changing implementation or registration. Evidence
directories must be outside the repository and must not contain input files.
Negative experiments and earlier implementation runs remain retained.

## Sources and historical-document mapping

These citations describe the adopted ideas; they do not retroactively change the
registrations or claims in documents 62–78. The NERVE clinical gym is the synthetic
task bank, controls and deterministic reward, not a validated clinical system.

- Docs 62–65 (validation/registration): [Vaccaro, Preregistration for Experiments with AI Agents](https://arxiv.org/abs/2606.11217); [Arize, how to prove each update](https://arize.com/resources/self-improving-agents/).
- Docs 66–76 (candidate generation, episodes and development): [Nakajima, Regimes](https://arxiv.org/abs/2606.10241), [Voyager](https://arxiv.org/abs/2305.16291), [Reflexion](https://arxiv.org/abs/2303.11366), [Darwin Gödel Machine](https://arxiv.org/abs/2505.22954).
- Docs 77–78 (holdout/transport): [Lewis, Scientific CI/CD](https://openreview.net/forum?id=4ob0d33A2l), as motivation for the new gate; the original fixed-slice registrations remain unchanged.
- Five-axis reporting and clinical-gym vocabulary: [Zhu et al., The Path to Self-Evolving Clinical Systems](https://arxiv.org/abs/2607.11175). Our accuracy measure does not establish clinical reasoning quality.
- Loop 47 hypothesis only: [Cammarata, Already Clean](https://already-clean.goodfire.com/). Toolkit and companion research review remain prerequisites; no claim of demonstrated circuit monosemanticity is made here.

DSPy/TextGrad/Trace, SEAL, ADAS/EvoAgentX and arbitrary self-rewriting remain
deferred as specified by the source plan. No adapter training or optimizer model
calls have been added. Protected gate, wallet, verifier and evaluator changes
remain outside every generator seam.
