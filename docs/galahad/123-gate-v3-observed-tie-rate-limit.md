# Gate v3: observed discordance and bank saturation

Doc122's **insufficient_power** verdict stands. This is a post-study CPU sensitivity analysis, not a new confirmatory validation, candidate evaluation or gate revision. Zero model calls, zero reserve access, no pod start and no continuation were performed.

The 100-item first stage was pre-declared, not an old harness cap accidentally applied. The signed selected design (`evidence/gate-v3-selected-design.json`, SHA256 `05d3b2c7e9e67f49dee8d1ac50b0c10d8623fbd4042093ff61c986ea6781efcf`) explicitly sets `primary.cap=100` and says “acceptance: latched; extension cannot create acceptance.” The signed source at43c3e78 has `primary_cap=100`, `main_cap=460`, `total_cap=500` and `risk_followup_items=40`. V5's prospective registration (`evidence/v5-gate-v3-study-registration.json`, SHA256 `f12a178767efc14a649a9bd265d1027f1f9578b88a281ec3fd8b5afc023b752f`) repeats these limits. Only primary acceptance enables balanced coverage sampling and the follow-up. There was **no deviation**. Continuing this terminal run to500 would change the signed decision procedure; it is not an available continuation under the existing signature. A mathematical e-process extension without resetting might preserve conditional-null validity under its assumptions, but that does not authorize changing the signed primary stopping rule after seeing outcomes.

The bet is0.3. Eight straight discordant wins yield `1.3^8 = 8.15730721`; **12**, not20, straight wins are needed to exceed E=20 (`1.3^11≈17.92`, `1.3^12≈23.30`). Ties add no evidence.

Observed counts from doc122 (no private items re-opened):

| Stratum | Items | v5 correct | v4 correct | Wins | Losses | Discordant pairs |
|---|---:|---:|---:|---:|---:|---:|
| supported-measurement | 12 | 12 | 12 | 0 | 0 | 0 |
| measurement-decoy | 11 | 11 | 11 | 0 | 0 | 0 |
| entity-decoy | 11 | 11 | 11 | 0 | 0 | 0 |
| unit-mismatch | 11 | 11 | 11 | 0 | 0 | 0 |
| conflict | 11 | 11 | 11 | 0 | 0 | 0 |
| multi-source-agreement | 11 | 11 | 7 | 4 | 0 | 4 |
| stale-vs-current | 11 | 11 | 11 | 0 | 0 | 0 |
| format-variant-agreement | 11 | 11 | 7 | 4 | 0 | 4 |
| dissenter | 11 | 11 | 11 | 0 | 0 | 0 |
| Total | 100 | 100 | 92 | 8 | 0 | 8 |

Dissenter, the registered risk stratum, showed **zero discordance** in its11 primary observations. No N40 follow-up occurred because primary acceptance was not reached. Its zero discordance does not itself block coverage: dissenter is a safety stratum covered by G1, not one of the six answer strata requiring ten pairs.

The registered CPU sensitivity uses the original main seed2026101801, H0 seed2026101802 and recorded risk seed2026101803, 10,000 streams per scenario, m10/t0, primary100/main460/total500 and risk40. Safety strata retain the recorded-zero-misfire, both-correct-tie fixture. Because overall92% ties does not specify their distribution, two fixtures were registered before simulation: (a) diffuse discordance0.12 in each of six answer strata, zero in safety strata, producing8% overall discordance; (b) concentrated discordance0.36 in each agreement stratum and zero elsewhere, also producing8% overall discordance. The latter preserves the observed support and normalizes the observed4/11 rates to the balanced nine-stratum schedule; it is a sensitivity assumption, not a claim of known population rates. Conditional both-correct probability on answer-stratum ties remains0.88, as in the signed fixture. Risk40 remains structural ties and needs no random draws.

| Fixture | Win probability among discordant pairs | Primary accepts /10,000 | Final good accepts /10,000 | Insufficient power /10,000 | Mean total items |
|---|---:|---:|---:|---:|---:|
| Diffuse, 92% ties | .85 | 195 (1.95%) | 0 (0%) | 10,000 (100%) | 107.80 |
| Diffuse, 92% ties | 1.00, never worse | 967 (9.67%) | 0 (0%) | 10,000 (100%) | 138.68 |
| Concentrated, 92% ties | .85 | 102 (1.02%) | 0 (0%) | 10,000 (100%) | 104.08 |
| Concentrated, 92% ties | 1.00, never worse | 613 (6.13%) | 0 (0%) | 10,000 (100%) | 124.52 |

All primary-accepted streams exhausted the coverage budget and received the registered40 risk items, finishing at500. Others stopped at primary100. No stream completed answer-stratum coverage; no good candidate was rejected by G1/G2. H0 final promotions were0/10,000 in both fixtures. These zeros are simulation observations, not proof of zero probability: a one-sided95% zero-success binomial upper bound is about0.030%. Thus the observed never-worse insufficient-power probability is100%, with an approximately99.970% one-sided lower bound within each simulated fixture.

A separately registered diagnostic ignores primary stopping and asks when balanced sampling would first produce ten discordances in **every** answer stratum. It does not change or continue the gate. Independent negative-binomial draws at the same main seed gave diffuse mean **1,045.8334** items, median1,024 and p90 **1,288**, before follow-up; adding40 gives mean1,085.8334. None of10,000 diagnostic streams covered by460 or even500. The rough60/.08=750 calculation accounts only for expected total discordances; the slowest of six strata makes joint coverage more costly. In the concentrated fixture, four required answer strata have structural zero discordance, so coverage has no finite completion time under that assumption. Observing zero in11–12 actual items does not establish structural zero in the real bank.

The vector simulation reuses the historical confirmation engine with only its input discordance fixture changed. Six hundred streams (100 per fixture/scenario) were independently replayed through the unchanged signed scalar `Process`; terminal decisions, primary acceptance and items consumed matched. Networking was disabled throughout. [Registration](evidence/gate-v3-92pct-ties/registration.json), [results](evidence/gate-v3-92pct-ties/result.json) and [receipt index](evidence/gate-v3-92pct-ties/index.json) bind the sources and simulated stream receipts. These are simulated scores, not new model measurements.

Registered finding: **discordance is a property of the candidate–incumbent pair and the bank**, not just candidate accuracy. The signed power tables assume75% overall ties and0.375 discordance in each answer stratum. They do not establish useful power at92% ties or when improvements are concentrated in two strata. Gate v3 can still enforce its signed safety, regression and evidence rules, but this sensitivity study shows negligible promotion power for this pair's observed tie pattern within500 items; non-promotion cannot establish equivalence or that v5 is no better.

The remedy registered here is **a harder, prospectively sealed bank v5 targeting v4's residual failure modes**, not a looser gate or a reset of this stream. Its design may use the published stratum counts, not held-out item identities or outputs; fresh templates and independent reserve generation must precede further candidate design. Harder agreement cases alone would not solve the four other answer-stratum coverage requirements. Bank v5 must be checked on development data for informative discordance across all required answer strata; a harder bank is not a guarantee this fixed pair can qualify. No bank was generated, no candidate was changed, and no further study or payload is registered by this finding. Stop here.
