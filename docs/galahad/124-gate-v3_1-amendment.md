# Gate v3.1: proposed scope-aware amendment

Status: **unsigned proposal**, not installed. Gate v3 remains canonical. Motivation is explicitly post-hoc to docs122–123; this amendment was registered before its simulations and before any new reserve study. No model calls or holdout item access occurred.

The requested “post-model-only, two-stratum” premise is not true of the frozen v5 implementation. V4 prepares the shared parser/prompt/schema and trusts decoded model value, unit and source on every eligible answer. V5 ignores raw model outputs and deterministically emits evidence value/unit and the smallest matching source for every eligible answer. It removes the inference path, not just a two-stratum postprocessor. Decimal equality already existed in the adapter. The same input bounds, parser, filtering and safety abstention logic are retained within the registered valid family-B contract. Tests provide schema-valid model-output counterexamples in all six answer strata, establishing that the seam can reach them even where this dev run observed perfect agreement.

Therefore v5's registered `affected_strata` is **supported-measurement, measurement-decoy, entity-decoy, multi-source-agreement, stale-vs-current and format-variant-agreement**. Only unit-mismatch, conflict and dissenter are structurally unaffected. No candidate change was made to manufacture a narrower scope. The two- and three-stratum simulation cells are hypothetical candidates requiring their own code proof; this payload does not authorize those scopes.

Doc106 replay used all900 candidate dev rows in the verified registered order, with source/input/schedule hashes checked. V4 decoded the recorded raw response; v5 evaluated the same query/evidence and ignored that raw response, exactly as its implementation does. No response was regenerated. Comparisons use canonical JSON bytes, not correctness alone.

| Stratum | Items | Byte-identical outputs | Numerically equivalent outputs | v4 correct | v5 correct |
|---|---:|---:|---:|---:|---:|
| conflict | 100 | 100 | 100 | 100 | 100 |
| dissenter | 100 | 100 | 100 | 100 | 100 |
| entity-decoy | 100 | 100 | 100 | 100 | 100 |
| format-variant-agreement | 100 | 63 | 68 | 68 | 100 |
| measurement-decoy | 100 | 100 | 100 | 100 | 100 |
| multi-source-agreement | 100 | 71 | 71 | 71 | 100 |
| stale-vs-current | 100 | 100 | 100 | 100 | 100 |
| supported-measurement | 100 | 100 | 100 | 100 | 100 |
| unit-mismatch | 100 | 100 | 100 | 100 | 100 |

All300 structurally unaffected safety outputs are byte-identical. The four other answer strata also match100/100 empirically, but remain affected because model-output changes can reach them. Multi-source agreement differs in29 source choices. Format-variant agreement differs in32 source choices and16 value strings (overlapping), with37 byte differences and32 semantic differences; the other five byte differences are numerically equivalent lexemes. Private row records stay outside Git; the aggregate receipt binds their hash. These are dev results, not grounds for promotion.

The proposed rule preserves alpha=.05, bet=.3, E>=20, primary100, m10, t0, main460, total500, primary futility and the unconditional N40 dissenter follow-up after acceptance. Primary sampling and coverage rotate over the pre-declared affected set only. Unaffected strata require both structural proof and a byte-identical replay before admission; any audited safety misfire remains a G1 zero-tolerance veto. G1 is not claimed to measure unsampled holdout strata. A missing proof, changed source or equivalence counterexample blocks admission. Domain and hard control checks remain required. The change narrows the tested population using proof, not observed wins, and cannot establish improvement outside that scope.

Simulations were registered before execution:10,000 streams per cell, original seeds2026101801(main)/2026101802(H0)/2026101803(risk), then fresh2026101901/2026101902/2026101903 with no intervening edits or tuning. Risk40 uses structural ties, so risk seeds are recorded but need no random draws. Both seed sets and all cells were fixed in advance. Tie rates64%/75% refer to the affected-only sampled population. Good p is conditional on discordance. The regression fixture has one affected stratum p=.30, all other affected strata p=.91875; its overall conditional p is .609375/.7125/.815625 for k2/3/6, respectively, not .85. Targets remain good(.85)>=80%, regressed non-promotion>=90%, H0<=5%, and observed harmful accept=0. Zero observed harmful acceptance is not proof of zero population risk.

| Seeds | Affected/ties | Good .85 | Good .90 | Regressed non-promotion | Neutral | Harmful | H0 | All targets |
|---|---|---:|---:|---:|---:|---:|---:|---|
| registered | k2-ties64 | 98.33% | 99.83% | 93.03% | 1.33% | 0.02% | 1.56% | no |
| registered | k2-ties75 | 85.29% | 95.28% | 96.11% | 0.62% | 0.00% | 0.68% | yes |
| registered | k3-ties64 | 98.06% | 99.81% | 89.49% | 1.21% | 0.01% | 1.38% | no |
| registered | k3-ties75 | 85.16% | 95.27% | 92.41% | 0.50% | 0.00% | 0.63% | yes |
| registered | k6-ties64 | 97.88% | 99.80% | 90.46% | 0.33% | 0.00% | 0.37% | yes |
| registered | k6-ties75 | 83.34% | 93.47% | 91.69% | 0.14% | 0.00% | 0.11% | yes |
| fresh | k2-ties64 | 98.14% | 99.81% | 93.09% | 1.37% | 0.00% | 1.21% | yes |
| fresh | k2-ties75 | 85.45% | 95.27% | 96.15% | 0.60% | 0.00% | 0.53% | yes |
| fresh | k3-ties64 | 97.90% | 99.76% | 89.76% | 1.20% | 0.00% | 1.12% | no |
| fresh | k3-ties75 | 85.35% | 95.26% | 92.64% | 0.56% | 0.00% | 0.47% | yes |
| fresh | k6-ties64 | 97.67% | 99.75% | 91.01% | 0.41% | 0.00% | 0.30% | yes |
| fresh | k6-ties75 | 83.44% | 93.31% | 92.26% | 0.14% | 0.00% | 0.09% | yes |

The six-stratum scope fixed by v5's code passes all targets at both tie rates on both seed sets. The k2/64% registered run had2 harmful accepts; k3/64% had1 and missed the regression target in both seed sets. Those failures are retained in the evidence, not tuned away or silently dropped. The proposed signing scope is the independently derived six-stratum v5 scope only. The simulation kernel was checked against the independent scalar amendment implementation on50 streams in each of72 cells (3,600 scalar replays); terminal verdict, primary acceptance, coverage and items agreed. Ten focused tests cover proof admission, reachable strata, scope scheduling, primary stopping, G1, G2, risk40, cap500, domain failures and duplicate IDs.

**Power limitation:** doc122's affected-only tie rate is59/67=88.06%, not64% or75%. This proposal does not establish80% power for that pair on bank v4. Removing the three unaffected safety strata changes sampling efficiency but does not remove the four other answer-stratum coverage requirements. A full-form signature would approve the bounded six-stratum procedure and its evidenced fixtures, not certify v5's efficacy or promise a promotion. The two-stratum shortcut cannot be justified by this code/replay.

Any future v5 evaluation would be a new prospectively registered stream on fresh bank v4 reserve, never continuation or reset of doc122. Its100 observations are consumed; all508 prior allocated slots are excluded, including408 quarantined unused slots. Ledger metadata shows148 unallocated items in each answer stratum and108 in dissenter, enough for at most77 per affected stratum plus40 risk observations under a500-observation cap. No allocation was made. Fresh reservation, seed, acceptance rule, controls, runtime identity and source hashes must be registered before the first future call; later allocations must also be excluded. The candidate remains unchanged and no retention is authorized.

The evidence, exact source and proposed protected-path manifest are bound by the separate signing payload. Gate v3 and its signature, registry, trust roots and existing protected manifest are unchanged; v2 remains retired. No signature or activation has been performed.

Simulation rates describe the paired gate kernel under its recorded safety fixture. An independent random-control outcome process is not simulated here. The mandatory always-abstain/random hard checks remain additional requirements of a future study and may lower its acceptance rate; these tables do not waive those checks.
