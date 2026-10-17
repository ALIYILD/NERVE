# SDK synthetic task/reward separation: 17 October continuation

This supersedes the oracle-fed development fixture for new SDK demos. Old v1 bundles remain immutable and require their source-pinned checkout. New v2 protocols were persisted before baseline predictions; git commit followed execution, so git order alone does not prove registration timing. All computation is deterministic CPU work with zero model calls.

| Domain | Wins / losses / ties | Candidate / incumbent / random / abstain | Bundle SHA256 |
|---|---|---|---|
| scientific | 34 / 0 / 66 | 100 / 66 / 53 / 0 | `724c0097e1a1f52e7524399dca2863668dd04dca6932c92ed929b57add78deec` |
| perfflux-sandbox | 34 / 0 / 66 | 100 / 66 / 43 / 0 | `63888cb2c142c77f6968b9c0362c587a4e01c93950178b36d8038a50a6dddc68` |
| clinicalos-sandbox | 34 / 0 / 66 | 100 / 66 / 41 / 0 | `218ec26d66aff8eaa329c804cd752c81d2fbb0111330d0b05a4f8b5a36c0c822` |

Each candidate is a hand-written context recovery rule and has zero safety-stratum errors in its 100-item synthetic bank. These SDK dev verdicts do not count as canonical scientific-family improvements or sealed promotions.

The public task projection removes truth, cluster and safety labels. Domain tasks are reported-delta extraction, synthetic latency choice, and synthetic literature metadata relevance. Inputs use seeded random values independent of item IDs. New tests mutate labels, safety flags, cluster labels and IDs, check separate seeds, enforce custom-domain rejection, and check source/protocol tampering.

The unchanged adaptation fixture directly supplies paired boolean rewards and injected served degradation. It is not generated from these new task evaluations. No real workload performance, clinician benefit or canonical scientific drift result is claimed. Signed evaluation fails closed; the proposal generator still has one repair template.

Initial demo generation and the first scientific replay overlapped an unrelated existing full test profile before the root agent requested serialized demo/replay execution. No timing measurements are claimed from those runs. Final validation was serialized under the shared test lock: all 13 SDK contract tests passed, followed by all three successful fresh-process v2 replays. The lock was released to the Family A replay worker. Full output: `receipts/sdk-v2-validation-20261017.txt`. Existing SQLite ResourceWarnings remain in inherited store code; no protected source was changed to suppress them.

The SDK tests include exact resume/restart receipt equality, signed-gate refusal, rejection memory, forged-candidate rejection, atomic learning retries, source/protocol tampering, and public/private input separation. The old v1 receipt files were not changed. All new evidence is confined to the three `receipts/loop-demo-v2-*-20261017/` directories.
