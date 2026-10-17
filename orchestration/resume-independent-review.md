# Independent continuation review — static only

Reviewed 2026-10-17: fast `5fbe6bd`; SDK `46320a2` / `30ddbcc`; A replay `88c84f4` / `d60ae1f`. No tests, demo evaluation, replay, network or model calls were run. No worker code, registry, trust or protected files were changed. This report does not validate generated outcomes or certify completion.

## Findings

No blocking correctness defect found in the changed execution paths by static inspection. One integration constraint must be preserved:

- **Pinned A replay cannot run from a checkout containing the SQLite patch.** `nerve-resume-a/scripts/replay_overnight_family_a.py:38-40` compares every historical `src/` and `scripts/` hash with the current checkout, including unrelated ARC and governed-learning files. The replay registration includes `src/nerve_awim/arc_execution.py` and `src/nerve_awim/governed_learning_v20.py`; both differ in `nerve-resume-fast`. A merged checkout will fail with `historical_source_changed` before scoring. Keep the original pinned A checkout for verification and explicitly document that execution boundary. Do not silently rebind historical provenance to permit integration. This is a predictable fail-closed restriction, not an incorrect result.

## Source review

SQLite: explicit `BEGIN IMMEDIATE` starts the transaction inside each `executescript`; the owning `_db` connection context commits on success and rolls back exceptions, then closes. The existing table and immutable-trigger definitions are unchanged. The three added tests address rollback after schema DDL and stable successful reopen. Performance and the full fast gate remain unverified here.

SDK: all changed evaluation and demo prediction calls apply the `public_input` allowlist. Predict receives only ID and a JSON-copied task; truth, safety and failure-cluster labels remain at the evaluator. The built-in predictors compute observable task rules. `get_domain` rejects subclass/custom contracts; this is not a user-extensible adapter implementation. Perfect candidate scores, if reproduced, establish synthetic rule-fixture correctness only. Adaptation still consumes a generated paired-reward stream and is accurately labeled legacy synthetic, not canonical D5. The demo pins protocol/source hashes before predictions; replay checks bundle, source and protocol bindings and recomputes a fresh temporary bundle. Hashes establish local reproducibility, not external signatures or retrospective-proof chronology.

A replay: original seed mismatch is acknowledged; this registers a distinct historical-reuse study. The runner checks exact tasks, nine strata, dev-only splits, historical schedule, model digest and seed, routed/prepared payload equivalence, original candidate-arm transport claims, bounded contiguous timeout retries and completion, then binds receipt bytes. W0 authorization is checked before bindings/evaluation; changed files/source/rule fail before scoring. Incumbent scoring explicitly uses canonical v3's checked deterministic-abstention route, not adapted_v1 outputs. The runner has no inference call and no registry/trust mutation. Registration decodes existing responses but does not calculate correctness. These facts cannot establish fresh-model evidence, unseen selection, independent confirmation or promotion.

## Protected integrity

Read-only SHA-256 verification across all three worktrees found 17/17 protected entries matching `docs/galahad/evidence/overnight-protected-paths.json` in each. This includes the tier manifest, registry and trust entries. The protected-path manifest itself has the same SHA-256 in all three worktrees: `107617543e1f9d289cde30d6c7e53dcc43f52c7fda3bcecb7221c56de6c9cf82`. Nothing in this review changed these paths.

## Pending independent evidence

The shared test lock remains reserved for the external W0 profile. The SDK's three v2 bundle/manifest pairs and documentation were uncommitted when inspected and were not replayed or outcome-audited. New tests have been inspected, not independently executed. A fresh-process SDK replay and authorized A replay, and actual exclusive fast-gate evidence, are still required before any completion claim.

## Committed evidence and expanded integrity audit

Follow-up reviewed SDK `322ea73eb581f9adc95be1d3094618be4fa4e764`, A `c86387b816e4c8c794caa0fd4a37ee8311131c8c`, and fast evidence head `2a0c3783f3dfbe900d0bed0ec0348ec4984dea33`. SDK source remains the previously reviewed implementation. Its committed validation log records 13 passing tests and three successful replay processes. A's verification record reports three passing guard tests and two replay processes. These are worker evidence, distinguished from the independent reruns below.

Independent read-only verification of the larger `nerve-orchestration/integrity-baseline.json` found **80/80 matching paths in each of the three worktrees**. Independently enumerated the complete registry/trust trees and compared every file byte with commit `b97aabf`: each tree has 23 files, with no added, removed or modified files and empty git diff. Machine-readable audit: `resume-independent-integrity.json`.

Independent outcome-byte audit verified all SDK bundle digests and checked A's registration/rows digests and exact equality of external rows/result with committed artifacts. Each SDK fixture records 34 wins, 0 losses, 66 ties and 0 safety errors; candidate 100, incumbent 66, random 53/43/41 (scientific/perfflux/clinicalos), abstain 0. A has 100 rows across nine strata, 59 wins, 0 losses, 41 ties, 0 safety errors; candidate 93, incumbent 34, random 10, abstain 34. Its recorded verdict is KEPT under historical reuse scope. Machine-readable audit: `resume-independent-outcome-audit.json`.

This supersedes the earlier observation that SDK bundles were uncommitted; it does not turn synthetic fixtures into workload evidence or historical outputs into fresh inference. No signing or promotion is authorized. Broader fast-gate results remain separate from the successful targeted worker tests.

## Independent fresh-process replay results

All four requested independent replays now passed serially under the shared lock. Full command, interpreter, stdout, stderr, return-code and A byte-hash evidence is saved in `resume-independent-replays.json`.

- Scientific SDK (Python 3.13): verified, zero model calls, bundle `724c0097e1a1f52e7524399dca2863668dd04dca6932c92ed929b57add78deec`.
- Perfflux SDK (Python 3.13): verified, zero model calls, bundle `63888cb2c142c77f6968b9c0362c587a4e01c93950178b36d8038a50a6dddc68`.
- Clinicalos SDK (Python 3.13): verified, zero model calls, bundle `218ec26d66aff8eaa329c804cd752c81d2fbb0111330d0b05a4f8b5a36c0c822`.
- A historical replay (the worker's existing Python 3.10): KEPT, 59/0/41, zero safety errors, both controls passed, zero new model calls. Registration, rows and result file bytes remained exactly unchanged after recomputation. Holdout remained closed and promotion unauthorized.

The first A attempt with Python 3.13 failed before execution because that interpreter lacks `cryptography`. It is retained in the evidence log. The successful isolated A replay used installed Python 3.10, which is below the package's supported interpreter range: this does **not** verify the whole package on a supported interpreter. No dependency installation, inference or full-suite execution was performed. The reviewer released its lock before the fast worker's separately authorized clean rerun.

Final integrity recheck at fast `6102dc4ff160677dfac40fb96c2e9983f23aa00a`, SDK `322ea73eb581f9adc95be1d3094618be4fa4e764`, and A `134a5b576789d989cc3838041761c140cd3d7ad9` again found all 80 baseline paths unchanged and all 23 registry/trust files byte-identical to `b97aabf`, with identical file sets. These pins supersede earlier intermediate evidence heads. A's post-study ingestion/proposal-generation additions were not independently executed in this review; its worker-reported 200 episodes, seven candidate failures, two proposal records and one unevaluated config must not be described as another evaluated improvement.

The successful replays establish reproducibility of the bounded SDK synthetic fixtures and A historical-dev reuse result. They do not establish a fast-tier pass, fresh model inference, production gains, independent unseen confirmation, signing or promotion. The earlier fast deadline run had external overlap; a clean rerun remains a separate pending gate and is outside this review's completion claim.
