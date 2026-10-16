# Two-stage stratum follow-up — registered simulation

The single-stage per-stratum veto design in doc 117 is retired as a design candidate. The primary e-process gate is not retired. This study replaces G2 with targeted escalation and corrects G1's synthetic safety fixture using recorded rule-gated behavior. No gate is installed; no signature or payload is prepared.

## G1 receipt fixture

The original Runpod v3 dev receipt, its retained dev dry-run bundle and holdout each record conflict 20/20 and unit-mismatch 20/20. They are listed separately, not pooled as independent trials. V4 dev records conflict, unit-mismatch and dissenter each 100/100; its holdout records each 11/11. Thus all observed abstain-stratum rule-misfire rates are zero. V3 supplies no dissenter evidence; v4 supplies it. The source hashes and aggregate-only export are in `evidence/two-stage-rule-gated-safety-fixture.json`. The original private dev receipt hash is bound by the retained dev bundle's reference hash; no new items are opened.

G1 remains zero tolerance against always-abstain per stratum. Always-abstain is correct exactly on the three abstain-expected strata, not an independent Bernoulli(.2) score. Candidate and current family-B incumbent both match the recorded correct abstentions there. A rule misfire would immediately create a G1 deficit; a fixture test injects one to verify rejection. The empirical fixture itself has zero misfires, so its G1 false-veto result must not be interpreted as a population zero-risk guarantee.

## Registered paired distribution and follow-up rule

Ten thousand streams per scenario; nine balanced rotating strata; primary cap 100 items, alpha=.05, bet=.3, futility E<=.05, minimum three net wins and observation of every stratum. The three abstain strata are all correct ties. On the six answer strata, discordance probability is .375 and both-correct probability conditional on a tie is .88. Averaged over strata, this preserves 75% ties, 70% both correct and 5% both wrong. Uniform answer-stratum p values are .85 for good, .50 for neutral and .35 for harmful. H0 uses a separate seed.

At primary e-process acceptance, any stratum with at least one net incumbent win triggers G2. There is no two-discordance minimum and no G2 primary veto. The verdict becomes **candidate_requires_review**, reason **stratum_follow_up**, until all targeted studies complete. Each triggered stratum receives N fresh independent paired items, for N in {20,30,40}. The N variants share nested independent follow-up prefixes; primary outcomes are never pooled into follow-up counts or reused as fresh data.

The pre-registered follow-up decision uses its N items only: net candidate loss rejects that stratum; net>=0 with at least one discordant pair clears it; zero discordance leaves candidate_requires_review with reason follow_up_insufficient_evidence. Every triggered stratum must clear. Follow-up can only filter primary acceptances, never resurrect a primary nonacceptance or restart its e-process. This is an explicit count decision, not a claimed statistical noninferiority test. All allocated follow-ups finish, even if another stratum fails, so simulated extra cost is N times the number of triggers.

The requested bad-stratum fixture sets one answer stratum to p=.30 and the other answer strata to .91875. Because the three safety strata now have no discordances, the actual overall discordant p is (.30+5*.91875)/6=.815625; assigning them a discordant p would contradict the empirical rule-gated fixture. A separately registered sensitivity sets the other five answer strata to .96, restoring overall discordant p=.85. Both are reported; the requested .91875 case remains the primary selection scenario.

Catch means a follow-up rejection identifying the deliberately bad stratum, divided by all bad-candidate streams. Also report catch conditional on that stratum being triggered, catch among primary acceptances and total nonpromotion; a primary insufficient_power result is not credited as a catch. Good trigger rates and expected extra items use all good-candidate streams as denominator, with conditional cost per triggered candidate separately recorded.

Selection is the smallest N with good acceptance>=80%, unconditional requested-scenario catch>=90%, and H0 false promotion<=5%. No parameter/seed search follows. If none qualifies, record chosen_N=null and stop. Performance assumes hypothetical full follow-up funding; actual bank-capacity constraints are separately applied and may leave the candidate under review.

## Reserve capacity

Only public sealed-manifest counts and existing consumed-slice metadata are used. Slices 2 and 3 together contain 200 nominally unused items: entity-decoy and measurement-decoy have 23 each; the other seven strata have 22 each. Before any primary sampling, this allows one N=20 follow-up per stratum, and zero N=30 or N=40 follow-ups. A balanced 100-item primary study from the same reserve leaves only 10–12 per stratum, insufficient for any requested N. Early primary stops use fewer, so per-candidate feasibility is checked against actual simulated stratum counts. A real gate custodian must verify live consumption before admitting a study; the manifest alone is not a live ledger.

Any shortfall leaves candidate_requires_review with reason reserve_shortfall; the harness does not silently reuse items or invent additional reserve. This simulation does not consume any reserve. Capacity receipt: `evidence/two-stage-bank-v3-reserve-capacity.json`.

The exclusive registration binds source, fixture and manifest hashes before research draws. Ten CPU fixture tests passed, including pending review, completion-only clearance, loss rejection, no primary resurrection, missing reserve, injected rule misfire, empirical G1 behavior, source binding, cost/catch accounting and safe-stratum ties. All work is simulated scores with network denied and zero model calls.

## Results and selection

No N meets all three registered targets. **chosen_N=null**. The single-stage guard is retired; the primary e-process remains a candidate for further design. No signing payload or canonical update is prepared. Each scenario uses 10,000 simulated streams. The following table assumes sufficient fresh reserve for every follow-up.

| N | Good accept p=.85 | Good follow-up trigger | Extra items per good proposal | Bad-stratum catch (all candidates) | Neutral accept | Harmful accept | H0 false promotion |
|---|---:|---:|---:|---:|---:|---:|---:|
| 20 | 85.31% | 11.88% | 2.422 | 33.50% | 0.56% | 0.00% | 0.58% |
| 30 | 85.36% | 11.88% | 3.633 | 36.20% | 0.57% | 0.00% | 0.55% |
| 40 | 85.40% | 11.88% | 4.844 | 37.70% | 0.58% | 0.00% | 0.56% |

G1 false-veto is **0/10,000 good streams (0%)** under the observed zero-misfire fixture, for every N. This is fixture-conditional, not a bound on future rule errors.

| N | Catch given bad stratum triggered | Catch among primary acceptances | Total bad-candidate nonpromotion | Extra items per triggered good candidate | Mean total items per good proposal |
|---|---:|---:|---:|---:|---:|
| 20 | 82.13% | 44.57% | 58.34% | 20.387 | 72.817 |
| 30 | 88.75% | 48.16% | 61.04% | 30.581 | 74.028 |
| 40 | 92.42% | 50.16% | 62.54% | 40.774 | 75.239 |

Only 4,079/10,000 requested-regression streams trigger follow-up on the bad stratum. Thus even perfect follow-up cannot yield 90% unconditional catch with this trigger. At N=40, 92.42% conditional catch does not establish 90% end-to-end catch. Even counting every nonpromotion as protection reaches only 62.54%. The binding issue is which candidates reach targeted testing, not merely follow-up length.

### Overall-discordant-p=.85 sensitivity

| N | Bad-stratum catch | Catch given bad stratum triggered | Total nonpromotion |
|---|---:|---:|---:|
| 20 | 40.29% | 82.01% | 53.26% |
| 30 | 43.75% | 89.05% | 56.72% |
| 40 | 45.37% | 92.35% | 58.34% |

This sensitivity also fails the 90% catch target at every N. It keeps the empirically all-tie safety strata and sets the five other answer strata to .96, as registered before simulation.

### Finite reserve

| Stratum | Nominal available items before primary | N=20 studies before primary | N=30 / N=40 studies |
|---|---:|---:|---:|
| conflict | 22 | 1 | 0 / 0 |
| dissenter | 22 | 1 | 0 / 0 |
| entity-decoy | 23 | 1 | 0 / 0 |
| format-variant-agreement | 22 | 1 | 0 / 0 |
| measurement-decoy | 23 | 1 | 0 / 0 |
| multi-source-agreement | 22 | 1 | 0 / 0 |
| stale-vs-current | 22 | 1 | 0 / 0 |
| supported-measurement | 22 | 1 | 0 / 0 |
| unit-mismatch | 22 | 1 | 0 / 0 |

These are upper bounds before consuming primary items, and require live ledger verification. Under simulated primary consumption from this same finite reserve:

| N | Good accept with reserve constraint | Good candidates held for reserve shortfall |
|---|---:|---:|
| 20 | 73.57% | 1187/10,000 |
| 30 | 73.56% | 1188/10,000 |
| 40 | 73.56% | 1188/10,000 |

No actual reserve items were read or consumed. The nominal bank cannot fund the advertised fully funded performance; fresh targeted reserves would be needed.

### Reproducibility

Registration SHA-256: `978a9e3e85e5aea2b39ec3591f1b7c4a29fceadf00829b90e9d0c6a75464fba1`. Result SHA-256: `9f20eb08c4e861c9e0acf7d75a132f4e0d1fdc4885c70fad08636e6057cf0ede`. Evidence: [registration](evidence/two-stage-followup-v1-registration.json), [results](evidence/two-stage-followup-v1-result.json), [verification and selection](evidence/two-stage-followup-v1-verification.json). Source hashes remained unchanged after the run. Ten fixture tests passed. Zero model calls; no signing, installation or payload.
