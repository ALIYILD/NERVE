# Outcome drift and rollback — 17 October 2026

Status: partial for canonical scientific D5. This CPU worker did not consume canonical scientific
bank items or model receipts. The implemented monitor,
router and crash recovery are exercised against an explicitly synthetic 1,200
item contract, not the requested family-A/v3 and family-B/v4 retained models.
There were no model calls, holdout reads, signatures or registry/trust writes.

The registered fixture contains four 300-item segments and a deliberately broken
served variant at indices 450–509. Thresholds and complete stream hash are
persisted before adaptation. CUSUM threshold 8, allowance 0.05, warmup 30, bounded
expected delay 60; router rolling window 20, margin 0.2, verification 10, quarantine 60.
The detector observes a fixed retained reference's correctness, discordance and
abstention. The router sees paired boolean outcomes and actual served correctness;
neither component receives the injected phase schedule or desired decisions.

Final trace (zero-based indices): detections 308/608/908, each 8 items after shift;
switch 312, verification 322; rollback 452 after three degraded served outcomes;
recovery switch 512, verification 522; switch-back 910, verification 920. Routing uses
only host-declared retained fixtures. Candidate development never changes them.
The 60-item quarantine prevents a drift signal from immediately re-enabling the
broken variant. Full-information rewards are required; no production bandit or
counterfactual estimation claim is made.

Evidence: `receipts/loop-demo-scientific-20261017/{bundle,manifest}.json`.
`python -m nerve_awim.loop replay receipts/loop-demo-scientific-20261017` rebuilds
the entire result in a fresh directory, including controls and stored learning,
and compares the bundle and source hashes. W3 fresh-process result is in
`orchestration/w3-scientific-replay.json`; independent W0 review is still required.

`scripts/verify_loop_restart.py` starts a worker, waits for 611 durable item
receipts, sends SIGKILL (returncode -9), opens the database in a new process and
resumes. `receipts/loop-restart-20261017/restart-proof.json` records 1,200 unique
receipts with a hash identical to the uninterrupted run and zero model calls.
SQLite commits each receipt and monitor/router checkpoint atomically. This proves
recorded-outcome restart behavior. It does not prove remote exactly-once inference.

Initial engineering fixture runs exposed detector baseline changes caused by
routing and premature unquarantine. These implementation defects were fixed before
the final registered receipt stream. These are development tests, not fresh
statistical confirmation seeds or an autoresearch keep-rule victory.

## Canonical dev-receipt feasibility audit

A read-only inventory after implementation checked the existing private **dev**
receipts; no reserves were opened. Machine-readable counts and source hashes are
in `orchestration/w3-canonical-drift-feasibility.json`:

| Existing measurement | Available | Missing canonical comparator |
| --- | --- | --- |
| Retained A-v3 original dev robustness | 700 unique tasks, four runs, 2,800 rows | B-v4 on those same tasks |
| B-v4 on bank-v3 dev (doc 106) | 900 tasks; 3,600 rows including controls | Unchanged retained A-v3 on those same tasks |
| B-v4 vs candidate v5 on bank-v5 dev (doc 127) | 100 tasks from two agreement strata | A-v3; another 200 scheduled hardened-B items for a distinct 300-item phase |

All three measured task-ID intersections are zero. The bank-v3 comparator named
`adapted_v1` is **not** the unchanged retained A-v3 policy. Its parser, prompt and
sampling seed differ (`scientific_family_b_adapter.py`; docs 87/92). Relabelling
those rows as retained A-v3 would invent counterfactual evidence. Candidate v5 is
not retained and cannot substitute for a routed skill. The older local v3 study
uses a 1.5B model and cannot substitute for the canonical 7B receipts either.

The original 700-task development corpus and the harder bank-v3 corpus are
separate banks; the plan's shorthand “family A: bank v3” needs an exact manifest
binding before a canonical study. Public compatibility evidence in doc 84 shows
that frozen A-v3 abstains on unsupported B grammar and can hit its bounded input
contract. A deterministic refusal may be freshly replayed and scored on CPU, but
it must be recorded as that policy's actual refusal/error under a registered
rule, not copied from adapted-v1 accuracy. Model-needed B-v4 outputs on A tasks
are still absent. Therefore the requested complete canonical 1,200-position
stream cannot currently be justified by recorded paired outcomes alone.

Minimum next study requirements:

1. Freeze the exact two retained descriptors, model digest, runtime, preparation,
   request body, decoder and scorer; bind the actual A/B/v5 **dev** manifests.
   Register the ordered 300/300/300/300 schedule, seed, controls, reward,
   detector thresholds and delay, verification/rollback rules and 60-position
   corruption intervention before observing new outputs. Specify whether final
   A reuses the first 300 tasks (900 distinct inputs) or uses 300 additional
   originals (1,200 distinct inputs). Reuse must not be described as independent
   observations.
2. Join existing receipts only on exact task/input plus policy/request, model and
   decoding bindings. Recompute deterministic gates without inference and record
   genuine abstentions/errors. Run only missing model-needed arm/task combinations
   on an authorized locked RunPod. In particular, acquire B-v4 on selected A
   tasks, A-v3 on B/v5 wherever its registered route actually requires inference,
   and B-v4 on the selected hardened tasks without matching receipts. A distinct
   300-task hardened phase can reuse at most the currently measured 100 v4 rows;
   at least 200 input positions need new evaluation (some may be deterministic).
3. Compute the call budget from the registered missing-request set. A conservative
   ceiling before reuse is 2,400 logical calls for two arms on 1,200 distinct
   inputs, plus up to two registered identical transport resends per call; it is
   not justified to assume the plan's approximately 600 calls. Exact savings
   depend on the chosen schedule, deterministic routes and byte-identical request
   matches. Existing daily cumulative call/spend limits still apply.
4. Replay-verify every raw outcome, build the paired correctness stream from actual
   predictions using the fixed scorer, then run monitoring/routing and the
   checkpoint-kill test. Inject degradation through a registered output mutation
   and rescore it, not by assigning an oracle incorrect flag. Truth is available
   to the scorer only, not the selected skill or routing decision.

Even after collecting these missing outcomes, three detections and a switch-back
are hypotheses, not guaranteed results. Original A-v3 measured perfect on its
original dev corpus; B-v4 may tie it there. If no retained skill is demonstrably
better after a phase change, preserving the current route is the honest outcome.
A forced switch from known phase labels would not satisfy D5.
