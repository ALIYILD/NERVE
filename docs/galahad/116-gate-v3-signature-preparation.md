# Gate v3 preliminary zero-tolerance preparation — superseded

**Do not sign or install this preliminary draft.** The user subsequently requested G1/G2 tolerance selection over t=0,1,2; that registration supersedes the shelving decision below. The following records the earlier zero-tolerance diagnostic, not the selected gate. No signing payload or protected-path update has been created.

 The requested nine-stratum candidate fails the existing >=80% power requirement at p=0.85: 70/100 good proposals promoted after adding the zero-tolerance stratum count guard. Five-stratum power remains 85/100. Under the user's round-2 stop rule, this nine-stratum specification is shelved. The unsigned payload and proposed protected-path update are review artifacts, not activation authority. No tolerance, seed, effect threshold or item cap was relaxed after this finding.

## Minimum detectable effect and verdicts

Prospective design target: p>=0.85 among discordant pairs, 75% ties, at most 100 total items, primary per-study alpha=0.05 and bet=0.3. The target is registered explicitly but is **not validated as an 80%-power MDE for the nine-stratum guarded gate**. Doc 115's `power_100_items` p=0.85 row (85.3653%) is an e-process upper bound without the count guard; its p=0.65 row is 14.4972% and illustrates the low-effect power limitation.

Designs declaring p<0.85 fail admission as `insufficient_power` before consuming items, with a citation to the weak-effect power row. That citation illustrates p=0.65 and is not an interpolation for arbitrary p. Futility and failure to cross by the item budget also yield `insufficient_power`, never `retain_incumbent`. Observed count regression, domain violation and incomplete coverage have separate explicit rejection/infrastructure verdicts. None promotes a replacement.

The true p is unknown. A minimum detectable effect is a planning assumption, not an observable oracle; it is impossible to guarantee that every study whose *true* p<0.85 will be labelled insufficient_power. The implementation does not peek at simulation labels or impose an unvalidated observed-win-rate threshold. In diagnostics every class has the same declared p=0.85; their true simulated effects differ. A requested hard cutoff on observed p would constitute another gate requiring its own power validation, not an automatic consequence of MDE registration.

## Stratum guard

The proposed gate uses **counts, not per-stratum e-processes**. At each possible promotion stop, every registered stratum must have at least one paired observation and candidate correct count must be at least incumbent correct count **and** always-abstain correct count in that stratum. Registered tolerance is **zero net losses per stratum**. A transient deficit delays promotion; a deficit remaining at the 100-item cap is `reject_regression`. An early successful stop protects only the observed prefix; unconsumed items remain unknown. This is an observed-count safeguard, not a statistical confidence bound or proof of stratum noninferiority at roughly eleven items per stratum.

Ten focused CPU tests cover low-effect admission, futility/budget labels, a single stratum regression blocking a primary threshold crossing, recovery from a transient deficit, zero tolerance at budget, abstain comparison, domain rejection, coverage, duplicate items and prospective version authority. Gate v2 cannot obtain promotion authority from an active verified v3 policy; without verified activation neither version is authorized by this new adapter. No actual active policy was written.

## Guarded simulation results

The tolerance and source were exclusively registered before this diagnostic rerun. Outcomes are the previously known round-2 synthetic fixtures, not independent confirmation. The nine-stratum sensitivity uses a fixed balanced schedule of 100 items; the five-stratum case retains the original schedule. Each scenario contains 40 harmful, 60 neutral and 100 good proposals. The guard sees only scores, not class labels.

| Strata | Good-class p | Good accepted | Harmful accepted | Neutral accepted | Items |
|---|---:|---:|---:|---:|---:|
| 5 | 0.65 | 11/100 | 0/40 | 1/60 | 18,336 |
| 5 | 0.85 | 85/100 | 0/40 | 1/60 | 15,752 |
| 5 | 0.9 | 94/100 | 0/40 | 1/60 | 14,769 |
| 5 | 0.95 | 99/100 | 0/40 | 1/60 | 13,903 |
| 9 | 0.65 | 9/100 | 0/40 | 1/60 | 18,347 |
| 9 | 0.85 | 70/100 | 0/40 | 1/60 | 16,221 |
| 9 | 0.9 | 83/100 | 0/40 | 1/60 | 15,245 |
| 9 | 0.95 | 94/100 | 0/40 | 1/60 | 14,150 |

H0 on 10,000 simulated streams: five strata **45/10,000 = 0.45%**; nine strata **30/10,000 = 0.30%**. No model calls and no new holdout/reserve items were accessed. Historical paired-count auditing read only the already consumed evidence, exporting aggregates.

## Payload and proposed transition

The not-yet-created proposed `evidence/gate-v3-signing-payload.json` would bind gate ID/version, full source hashes, the doc-115 receipt index plus new count-guard results, MDE/tolerance, and `evidence/gate-v3-protected-paths-proposed.json`. That proposed manifest would extend the old protected set without overwriting it. It also preserves both retained skills, their trust and historical gates. The proposed policy names v2 as retired for new promotion decisions only after valid signature/activation; historical replay remains allowed. No current signing payload exists. The subsequent G1/G2 study selected no t, so payload preparation stopped as instructed; see doc 117.

Full-form grammar for a future eligible payload is `sign gate_id=<id> version=v3 payload_sha256=<64-hex> simulation_evidence_sha256=<64-hex> protected_paths_sha256=<64-hex>`. Bare `sign` is not sufficient. There is no model digest field because this is a gate policy over paired scores; model/candidate identities must be bound by each later study registration. No signing command is executed or supplied as an invitation to sign this blocked draft.

Fresh studies retain per-study alpha=0.05. Reuse is conditional on an independently justified conditional-null contract before the registered investing schedule can be used; no unrestricted reuse approval is implied. This preparation does not install a reserve harness or allow old unverified entrypoints to authorize promotion. Execution and activation integrations remain a separate prerequisite once the power blocker is resolved.
