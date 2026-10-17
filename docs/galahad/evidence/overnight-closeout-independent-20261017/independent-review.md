# Independent overnight review — 17 October 2026

**Partial delivery; integration remains unverified.** All six pods are independently confirmed EXITED. The final supported-Python exclusive fast tier timed out at its unchanged 180-second bound. No sealed promotion or original harmful0 gate qualification was achieved.

Review covers W1 46b0f2d, W2 f95cdd8 plus final B01b receipts, W3 564d213, and isolated W0-final protected files. Reviewer ran zero model inference, changed no pods, read no sealed item outputs and performed no signing or activation. Temporary CPU stores and review logs were written. Live infrastructure access was a read-only RunPod MCP list_pods call. Replay batches used atomic shared test.lock acquisition and finally-release; an acquisition during W0's exclusive run failed before executing any replay, then succeeded after release.

## Independently verified evidence

- All 80 baseline protected hashes match across initial W0–W3 and final isolated W0-final. Registry/trust diffs against b97aabf are empty. Canonical v3 signature verifies.
- Gate replay: 390 indexed hashes, 186 receipt cells, 1,860,000 aggregate rows and nine harmful scalar cases match. This checks aggregate counts across all streams and scalar outcomes for the nine harmful cases, not a scalar rerun of all 1.86M streams. All m values still fail original harmful0. `independent-gate.log`.
- Historical B replay recomputed 100 dev rows from request claims/wire outputs, validated task truth/evaluator pins and imported 100 episodes into a temporary companion store, producing two failure clusters. `independent-historical-b.log`.
- **Fresh B01b replay passes:** 100 claim-bound receipts; 35 wins, 0 losses, 65 ties, zero scoped safety errors, both always-abstain/random controls beaten. Recorded execution: 100 model calls, 198.89927053503925 seconds. Registration SHA256 `094e6058bac759f3a16824f1124b8f9fd4c5a2cacccb9c6fe84cdae5a873e568`; row hash `8a473ba29926766252ef62d9f9c2e7f14b5d332aff43f5bd006d9ec6cb387497`. Independent replay blocked network/subprocess, intercepted writes, and compared to immutable replay.json without modifying source receipts. `independent-B01b-replay.json`. This keep covers only the two registered answerable agreement strata, not broad Family B safety or Family A improvement.
- W3 564d213: all three updated scientific/PerfFlux/Clinical OS bundles independently reproduce bundle/source hashes. Fresh SIGKILL at checkpoint 611 resumes to 1,200 unique receipts identical to uninterrupted execution, zero inference. `independent-fixed-{scientific,perfflux-sandbox,clinicalos-sandbox,restart}.log`.
- Independent live RunPod MCP list_pods returns all six EXITED, no next page: `5xndo7i7s5r9zn`, `ki9m7vdg9qsea6`, `lvojhtouu5gede`, `b7qj6qyx9ij6gg`, `97vr620wnmtuga`, `lg0svvuenxvbno`. `independent-final-pods.json`.

## Findings and resolution

1. SDK learn originally committed its local store before companion ingestion. Reproduction `learn([a,b]); learn([b,a,c])` raised `conflicting_episode_id` but left counts 3 versus 2 (`independent-learn-consistency.json`). **Resolved in 564d213:** one authoritative transaction, stable item identity, legacy dual-store directories explicitly rejected. Original reproduction now succeeds with three episodes, and a mixed new/conflicting batch completely rolls back (`independent-fixed-learn.json`).
2. W2 eager executor.map originally queued all 100 tasks and could continue work after a failure. **Resolved in f95cdd8:** at most four submitted futures, worker cancellation event, no replacement admission after error. Reviewer inspected fix; worker's three focused cancellation tests passed.
3. W3 documentation incorrectly said the protected tier manifest prevented fast-tier inclusion. **Resolved in 1d01cb8:** all discovered non-slow modules automatically enter fast; no manifest edit is needed. SDK tests add runtime and integration remains subject to the unchanged deadline.

## Fast-tier result and shutdown accounting

Earlier Python 3.10 attempt was below supported package Python and timed out. An earlier Python 3.13 attempt was contaminated by W3's admitted mkdir-p lock mistake/overlap and also timed out; neither is valid passing-suite evidence. W3 stopped and documented that violation.

The final Python 3.13 attempt held the lock exclusively, retained the protected 180-second bound, and exited124 at 00:08:13 UTC. `~/nerve-orchestration/preflight-fast-exclusive.log` ends `fast gate exceeded 180s wall deadline`. This is the valid unresolved preflight result, not a passed test count. W0 counted the third infrastructure failure and wrapped early; no subsequent experiments were authorized. Final merge/integration must not be represented as verified.

Closed conservative request-time compute intervals independently recalculate to **$0.2084487305027778**, with **112 calls = 12 preflight + 100 B01b**. These are operational accounting estimates, excluding storage. The saved provider billing snapshot reports $0.06747213110793382 ($0.06457861233502626 GPU + $0.002893518772907555 disk) for six records in the 23:00–00:00 UTC bucket, despite its query ending01:00. It includes other pods and omits the completed 00:00 B-study interval; it is not a reconciled final invoice and must not replace/add directly to the operational estimate. EXITED is independently verified; final provider billing remains pending.

## Signing queue and external work

The queue was initially empty. An external concurrent process subsequently committed49bbe7b in W0 and inserted `gate-v3.2-bounded-harmful-m14-4e2a5addbcc5`. That commit/entry was preserved; this run isolated W0-final instead. Do not attribute the external proposal to this run.

Its full-form string matches the external entry's own gate ID/version, payload hash, simulation evidence hash and proposed protected manifest hash. **It is not field-complete against the original requested gateid/version/sourcehash/evidencehash/protectedhash form:** there is no explicit source_sha256 field in the string. The payload does contain a source hash, so signing that payload would bind it indirectly; that is not the same as satisfying the requested explicit full form, nor is it proof of compatibility with the pinned v3 signer. Payload/source/evidence/design/table hashes verify (`independent-external-queue-check.json`). Payload hash is `4e2a5addbcc56117a9971e67152b632f63536d9341bf92909e56b81fb83a0d5f`. It explicitly reformulates post-doc129 qualification to marginal per-profile harmful-rate 95% upper bound <=0.0005. **This does not satisfy original harmful0/D4.** It remains unsigned/uninstalled and is a gate proposal, not a sealed candidate promote_proposal; D3 is not met. Reviewer verified hash bindings, not the external statistical study itself. No signature is recommended by this review.

## Final D1–D8 assessment

| Deliverable | Status | Evidence and limitation |
|---|---|---|
| D1 | Partial | Historical B100 and completed B-study200 episodes ingested in explicit companion; two initial proposals and no next failures in kept B fixture. Three autonomous proposals per family not established. A-route audit reports900 actual bank-v3 dev deterministic abstentions,300correct/600wrong; its ongoing ingestion is not yet independently replayed. |
| D2 | Partial | B01b narrow-stratum keep independently verified; no Family A dev keep. SDK truth-aware fixture keeps do not substitute. |
| D3 | Not achieved | No sealed promote_proposal; external unsigned gate queue entry is unrelated. |
| D4 | Not achieved | Original registered/fresh-seed gate grid fails harmful0 at every m. External relaxed criterion is distinct. |
| D5 | Partial | Registered1200-item synthetic drift and SIGKILL recovery verified; canonical scientific model/bank stream absent. |
| D6 | Achieved in synthetic contract scope | Both sandbox receipts replay. Shared deterministic fixtures/full-information paired rewards; no real workload or clinical reward evidence. |
| D7 | Partial overall | Five interfaces, CLI, controls, three domains and hashed replay implemented; identified SDK defects fixed. Synthetic API contract verified, integrated fast/CI gate unresolved; no real reward integration. |
| D8 | Partial | Independent replay, protected hashes, shutdown and estimate verified. Exclusive fast tier fails deadline; final verified merge unavailable; provider bill unreconciled. |

All scientific/sandbox evidence remains synthetic. Retained fixtures are host-declared and the demo candidate reads synthetic truth. These runs establish implementation mechanics and scoped dev outcomes, not clinical benefit, real PerfFlux performance, production online-bandit learning or exactly-once remote inference. Original protected bank ledgers/reserve files were not altered by the reviewer.
