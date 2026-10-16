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
