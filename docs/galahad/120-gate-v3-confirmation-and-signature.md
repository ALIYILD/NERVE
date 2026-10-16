# Gate v3: fresh-seed confirmation and unsigned signing payload

**Signed and canonical.** The user supplied the exact full-form authorization; signature verified at 2026-10-16T21:20:26.890441+00:00. Gate v3 is active in the canonical promotion registry; gate v2 is retired for new promotion decisions and remains available for historical replay. Both retained skills stand unchanged. No inference or holdout consumption occurred.

The preparation narrative below records the pre-signature state; immutable payload/evidence/proposed-manifest bytes remain unchanged.

**Selected m=10, t=0, unconditional risk follow-up N=40, total cap500.** It is the smallest registered m meeting all four observed confirmation targets. Bank v4 is generated and sealed. The signing payload and proposed protected-path update are prepared, unsigned and unapplied; nothing is installed or activated.

## Prospective registration and post-hoc metric clarification

The user explicitly changed doc119’s gated regression metric to **non-promotion by any route**, including primary nonacceptance, G1, G2, risk follow-up and coverage-cap insufficient_power. This is a **post-hoc clarification of the earlier catch metric**, registered before the new confirmation draws. Doc119’s identification results are preserved and not relabelled as prospective nonpromotion evidence. Identification remains reported, not gated.

Fresh seeds: main2026101801, independent H0 main2026101802; risk-follow-up seed2026101803 is reserved but needs no random draws because its registered dissenter fixture is deterministic. Ten thousand streams per scenario, common potential scores across m=8,10,12, no seed search or retuning. Registration binds the implementation, tests, fixture, prior vector simulator and v5 specification. Source hashes are unchanged after confirmation.

Pooled gate unchanged: alpha=.05, bet=.3, E<=.05 futility, at least three net wins and observation of all nine strata, primary cap100. Acceptance is latched. Then balanced sampling across all nine strata continues until each of the six answer strata has m discordances, including primary observations. G2 evaluates cumulative answer-stratum net losses once at completed coverage, with t=0. The three safety strata are structural ties under the recorded-misfire fixture and covered by G1 alone, zero tolerance.

Cap500 includes the unconditional40: main coverage uses at most460 items, then every primary-accepted candidate receives40 fresh risk-stratum items regardless of observed G2 losses or incomplete coverage. Actual safety/domain failures stop immediately. Failure to complete coverage cannot promote. There is no later pooled-e crossing or resurrection of a primary nonacceptance.

**Registered risk is dissenter**, taken from v5 doc113, not a post-outcome choice of an answer stratum. Its all-correct safety follow-up passes G1 with no discordance requirement; zero discordances do not create an impossible admission condition. Follow-up samples are not pooled into G2 or the e-process. On this fixture it adds zero marginal regression identification, costs40 per primary acceptance, and remains a safety check. The confirmation does not claim equal power for arbitrary different risk strata.

As in doc119, safety strata have no discordances; six answer strata have .375 discordance probability, preserving75% overall ties. Regression has one answer stratum p=.30 and other answer strata .91875, so effective overall discordant p=.815625. The requested fixture is unchanged; no claim that its overall discordant p=.85 is made.

## Confirmation performance table

All rates use10,000 proposed studies per scenario. False veto means actual G1/G2/follow-up rejection of good candidates; primary futility and incomplete coverage are not counted as false veto.

| m | Good p=.85 | Good p=.90 | False veto .85 / .90 | Regressed non-promotion | Stratum identification | Neutral accept | Harmful accept | H0 false promotion | Qualifies |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 8 | 85.47% | 95.76% | 0.63% / 0.09% | 89.17% | 64.39% | 0.16% | 0.00% | 0.20% | no |
| 10 | 85.18% | 95.03% | 0.24% / 0.02% | 92.12% | 66.76% | 0.13% | 0.00% | 0.19% | yes |
| 12 | 81.02% | 90.15% | 0.13% / 0.00% | 94.34% | 65.44% | 0.09% | 0.00% | 0.18% | yes |

Selection targets were good p=.85>=80%, regressed nonpromotion>=90%, H0<=5%, observed harmful accepts=0. M=8 fails nonpromotion; m=10 and12 pass; choose10. Zero harmful accepts means observed0/10,000, not proof of population zero harm. G1 false veto is0 under the empirical zero-misfire fixture, not a population safety guarantee. H0 is per-study, not across-study FWER.

## Item, wall-clock and cost table

Historical measured A40 throughput rounded to2.3–3.4 seconds per item **across all arms**, at historical$0.59/hour. Each row includes the risk40, primary nonacceptances and coverage failures. Mean and p90 are over all proposals in that scenario. Startup, calibration, retries, idle and storage excluded; no current pricing lookup or GPU start occurred. These are conservative all-arm projections, not measured v5 runtime (v5’s deterministic rule may avoid model calls).

| m | Scenario | Mean items | p90 items | Mean minutes | p90 minutes | Mean compute USD | p90 compute USD |
|---|---|---:|---:|---:|---:|---:|---:|
| 8 | H0 | 97.13 | 100 | 3.72–5.50 | 3.83–5.67 | $0.0366–$0.0541 | $0.0377–$0.0557 |
| 8 | good_085 | 271.28 | 354 | 10.40–15.37 | 13.57–20.06 | $0.1023–$0.1512 | $0.1334–$0.1973 |
| 8 | good_090 | 291.91 | 359 | 11.19–16.54 | 13.76–20.34 | $0.1100–$0.1627 | $0.1353–$0.2000 |
| 8 | harmful | 77.89 | 100 | 2.99–4.41 | 3.83–5.67 | $0.0294–$0.0434 | $0.0377–$0.0557 |
| 8 | neutral | 96.75 | 100 | 3.71–5.48 | 3.83–5.67 | $0.0365–$0.0539 | $0.0377–$0.0557 |
| 8 | regression_requested | 248.34 | 346 | 9.52–14.07 | 13.26–19.61 | $0.0936–$0.1384 | $0.1304–$0.1928 |
| 10 | H0 | 97.55 | 100 | 3.74–5.53 | 3.83–5.67 | $0.0368–$0.0544 | $0.0377–$0.0557 |
| 10 | good_085 | 319.54 | 415 | 12.25–18.11 | 15.91–23.52 | $0.1204–$0.1781 | $0.1564–$0.2312 |
| 10 | good_090 | 345.51 | 420 | 13.24–19.58 | 16.10–23.80 | $0.1302–$0.1925 | $0.1583–$0.2340 |
| 10 | harmful | 77.90 | 100 | 2.99–4.41 | 3.83–5.67 | $0.0294–$0.0434 | $0.0377–$0.0557 |
| 10 | neutral | 97.11 | 100 | 3.72–5.50 | 3.83–5.67 | $0.0366–$0.0541 | $0.0377–$0.0557 |
| 10 | regression_requested | 290.34 | 408 | 11.13–16.45 | 15.64–23.12 | $0.1094–$0.1618 | $0.1538–$0.2273 |
| 12 | H0 | 97.96 | 100 | 3.76–5.55 | 3.83–5.67 | $0.0369–$0.0546 | $0.0377–$0.0557 |
| 12 | good_085 | 365.98 | 475 | 14.03–20.74 | 18.21–26.92 | $0.1380–$0.2039 | $0.1790–$0.2647 |
| 12 | good_090 | 397.06 | 480 | 15.22–22.50 | 18.40–27.20 | $0.1497–$0.2212 | $0.1809–$0.2675 |
| 12 | harmful | 77.91 | 100 | 2.99–4.41 | 3.83–5.67 | $0.0294–$0.0434 | $0.0377–$0.0557 |
| 12 | neutral | 97.41 | 100 | 3.73–5.52 | 3.83–5.67 | $0.0367–$0.0543 | $0.0377–$0.0557 |
| 12 | regression_requested | 331.16 | 468 | 12.69–18.77 | 17.94–26.52 | $0.1248–$0.1845 | $0.1764–$0.2608 |

For selected m=10 and good p=.85: mean319.5427 items, p90=415. Hard maximum500 projects19.17–28.33 minutes and$0.1885–$0.2786 study compute. This authorizes no inference or pod spending.

## Bank v4: eligible fresh holdout reserve

Manifest SHA-256: `8ae1b71b421fe8ace9b89dff0bcc359c79b7d535960306e0640da76fdba79aeb`. Version `task-bank-v4-family-b-reserve`: **900 dev +1,800 reserve**, nine strata, exactly200 reserve per stratum, no consumed items. New cryptographic private seed and v4 HMAC namespace; independent truth validation of all2,700 items; exact task-ID and query/evidence uniqueness within the new bank. New namespace/seed provides cryptographic separation from prior banks without opening their private reserves.

Generation registration preceded generation, records source hashes and confirmation qualification, and bound doc113/v5 registration before any new bank item existed. V5’s specification was verified byte-for-byte against committed ancestor `5b003896d9cca3550e110186998d4054452d1a26` (16 Oct2026 20:36:13+01:00). Its existing source specification was not changed in response to this bank. The earlier bank-v3/200-item evaluation protocol in doc113 remains historical: a prospective study addendum binding bankv4 and gatev3 is required before execution; no silent migration or reserve access is authorized.

Generation/validation/write/sealing took **3.159 seconds**, zero model calls, zero GPU hours and$0 cloud compute. Sealed at `2026-10-16T20:52:46.234627+00:00`. Private custodian directory: `/Users/aliyildirim/nerve-research-runs/scientific-bank-v4-20261016` (0700); seed and all18 dev/reserve item files are000. Only registration, manifest and aggregate sealing receipt are published. This is the eligible private bank, distinct from doc119’s public-seed capacity benchmark. Trusted host permissions are the boundary, not an independent enclave.

With main cap460, balanced sampling consumes at most52 per stratum; a40-item dissenter follow-up consumes at most92 on that risk stratum per full study. Two worst-case full studies fit its200-item reserve, leaving at least16; a third is not guaranteed. Fresh allocation and atomic consumption must be enforced by a gate custodian before any evaluation. Bank creation alone does not grant execution authority.

## Prepared signature and canonical policy

Gate ID `scientific-paired-sequential-promotion`, version`v3`. Source SHA-256: `2e643b6472deb22ec56e9ea25ad4aab9a0cce4b9592b548fed824e4f5f089a54`. Payload SHA-256: `c1dab32c453609ce2cae72a7c3b660874f243b1f2e67bebde8c9463d44de22d8`. Evidence-index SHA-256: `4a988dbd4ce59638eebc71473dbaf0923b3454b00d78f822bfd2037bdd587315`. Proposed protected-path manifest SHA-256: `0e102563b9c72a700e07657ab5993656ff06b2d913b8846d647e258ab019fcc1`.

The evidence index binds exact bytes of docs114–119, their linked historical receipts, the new registration/results/verification, selected design, both tables and bank metadata. The proposed protected manifest extends the existing set without overwriting it and preserves both retained skills. Source is a pure, unsigned implementation; no production selector or current canonical gate was replaced.

On valid full-form signing and activation, **gate v2 is retired for promotion decisions** (historical replay remains allowed), recording its47.18% H0 false-promotion rate and43.33% neutral acceptance in doc115’s simulation fixture. **Existing v3 and v4 promotions stand unchanged**, with paired audits80/0 and21/0 wins/losses respectively. Those audits support their large measured effects; they are not a retrospective claim of evaluation under gatev3.

Nine tests passed, including exact scalar/vector agreement over45 streams×6 scenarios×3 m values, safety failures, risk completion, the500-item cap, unchanged primary cap, terminal G2 semantics, unique fresh items, balanced scheduling and unsigned authority. All17 original protected hashes and7 family-B retained-file hashes match. Confirmation rates/costs and payload/source/evidence/manifest hashes were reconciled; [preparation verification](evidence/gate-v3-payload-preparation-verification.json) checked all38 evidence files and67 proposed protected paths. Historical count-guard replay uses its frozen earlier source revision; it is not the current confirmation harness.

[Signing payload](evidence/gate-v3-signing-payload.json) · [Registered selected design](evidence/gate-v3-selected-design.json) · [Both machine-readable tables](evidence/gate-v3-confirmation-tables.json) · [Evidence index](evidence/gate-v3-signing-evidence-index.json) · [Proposed protected-path update](evidence/gate-v3-protected-paths-proposed.json) · [Full-form signing instruction](evidence/gate-v3-signing-request.txt).

**Stop point: awaiting the user’s full-form signature. No signature, installation, canonical pointer change, model call or holdout consumption occurred.**

## Signature and canonical consumer record

Exact user authorization:

```text
sign gate_id=scientific-paired-sequential-promotion version=v3 payload_sha256=c1dab32c453609ce2cae72a7c3b660874f243b1f2e67bebde8c9463d44de22d8 simulation_evidence_sha256=4a988dbd4ce59638eebc71473dbaf0923b3454b00d78f822bfd2037bdd587315 protected_paths_sha256=0e102563b9c72a700e07657ab5993656ff06b2d913b8846d647e258ab019fcc1
```

The operator-authorized local Ed25519 signature is executed by Codex with a newly generated delegated key, not the user’s personal key. Private key stays outside Git in a mode0700 directory, key0600. Independent host trust and its public mirror bind the reviewed payload, canonical policy, signer and loader. A signed registry was atomically published only after staged signature/binding verification.

Registry: `registry/scientific-promotion-gate-v3`. The canonical loader enforces the reviewed protected manifest and evidence hashes, fixes m=10 and risk=dissenter, refuses v2 for new promotions and rejects item reuse. It creates proposals only: it does not automatically sign candidate skills or authorize inference. Existing historical evaluation implementations remain unchanged for replay.

Signed-record SHA-256: `fc0508917dbe176132f58aababd4087eae948e65f425a1f96cd4b5d10a2d11aa`. Trust SHA-256: `1d33037129a5a179fbc8357c4136dbbf018327f4b54240280fdd3fb3ef8c4ea8`. Payload remains `c1dab32c453609ce2cae72a7c3b660874f243b1f2e67bebde8c9463d44de22d8`. The original payload retains its preparation-state flags; signed status and canonical selection live in the separately signed registry record and policy, avoiding changes to the authorized bytes.

Fresh isolated-process verification passed: signature/trust/evidence, canonical consumer, v2 refusal and reuse refusal. The synthetic consumer fixture completed with m=10 and40 risk items, with no model calls or real reserve access. Eight signer/tamper tests and nine gate/simulator tests passed. Bank-v4 ledger remains zero consumed/zero allocated.

[Signing receipt](evidence/gate-v3-signing-receipt.json) · [Fresh-process consumer proof](evidence/gate-v3-signed-consumer-verification.json).
