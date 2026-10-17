# W3 status — 2026-10-17

L5/L6 implementation: in progress; cost $0, model calls 0. Existing
`goal_orchestrator.py` and `adaptation*.py` are byte-identical to 530591c, so no
selective cherry-pick of those modules was needed. W2 companion study-v2 schema
was cherry-picked without changing the protected original v2 module.

Verification deviation: first test suite mistakenly used `mkdir -p` for the
shared lock and overlapped W0's suite. W0 notified W3; W3 immediately interrupted
its process. That run is not counted as validation. Subsequent suites require
atomic `mkdir` success and Python 3.13. No GPU or laptop inference occurred.

Boundaries: the scientific CPU contract is synthetic and not canonical bank
replay; no canonical D5 claim. Sandbox routing is full-information over retained
fixtures, not an online production bandit. Signed gate evaluation fails closed.

L5/L6 completed on the synthetic contract scope. Verdict kept for each dev
fixture; calls 0, cost $0. D5 partial because canonical scientific bank/model
stream was not run. D6 synthetic contract demonstration achieved. D7 interfaces,
three domains, CLI receipts, replay and docs implemented. SDK tests are
automatically discovered in the fast tier because they are absent from
slow_modules; no protected manifest edit is needed. The dedicated suite passed,
but W0 reported the full fast tier timed out at its 180-second deadline, so full
fast-tier completion remains unverified. One candidate template only, so this
does not establish scientific three-proposal autonomy or sealed improvement.

Validation: six dedicated SDK tests passed under Python 3.13 in 52.543 seconds
with atomic test.lock held; inherited ExperienceStore SQLite ResourceWarnings
remain visible in w3-sdk-tests.log. Three fresh-process replay bundles verified.
SIGKILL at checkpoint 611 resumed to 1,200 unique identical receipts, zero calls.
Detections 308/608/908; switches 312/512/910; one rollback 452. Protected paths
80/80 unchanged at completion. Existing inherited source hashes and all study
IDs are in w3-source-integrity.json and w3-studies.json respectively.

Code commit 942ebbe pushed to ALIYILD/NERVE overnight/w3-adapt-sdk. Final evidence
commit follows. No signatures, retention, activation, holdout reads or external
repository writes. No pods started or used by W3.

Reviewer correction: the earlier claim that SDK fast-tier integration required
a protected manifest edit was incorrect. scripts/timed_test_runner.py selects
all discovered modules absent from slow_modules. Only the full-tier timeout
remains a verification limitation. Signed API evaluation still fails closed;
sealed studies require the external signed gate, and no SDK method signs.

Independent review found an ingestion atomicity defect: local episode writes
could precede a companion failure, and positional ordinals made reordered retries
conflict. Corrected by removing duplicate episode storage, using explicit stable
source ordinals, and committing the entire bounded batch in one companion
transaction. No protected original v2 file changed. Added reorder/retry/restart,
late conflict after 1,001 new records, byte-unchanged failure, large valid batch,
and changed-ordinal regression coverage. All three bundles were regenerated and freshly replay-verified; prior local
checkpoints are preserved outside the worktree. Eight SDK tests passed in
30.129 seconds with the atomic test lock held. The lock is now released.
SIGKILL proof regenerated successfully; 80 protected hashes remain unchanged.
