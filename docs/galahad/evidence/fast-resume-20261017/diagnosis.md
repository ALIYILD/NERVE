# Fast-tier continuation diagnosis

The original exclusive run timed out at 180 seconds during the first ARC evaluation test, after the preceding alphabetically ordered test modules. A separate original ARC evaluation probe was killed after 60.153 seconds. These observations identify a hotspot, not a passing gate.

The frozen manifest has `new_modules_default=fast`: the recorded discovery diagnostic counts 2,282 fast tests versus 2,044 total tests at the manifest's original measurement. ARC evaluation is one of the new modules. Changing the protected partition or increasing the fast deadline is outside this continuation.

`arc_evaluation._run_benchmark` executes 30 development episodes, 90 validation episodes across three candidates, and 180 three-arm benchmark episodes: 300 separate workflow stores for one test. Every workflow creates a GovernedLearning schema (seven tables) and ARC schema (five tables and one trigger). Previously these 13 DDL statements each ran in SQLite autocommit: a connection's Python context manager does not begin a transaction for `executescript`.

The proposed patch starts a transaction inside each of these two schema scripts. The existing `_db` context commits on success and rolls back on exception. This reduces schema commit boundaries from 13 to two per workflow, without changing SQLite synchronization, stored schema, evaluator settings, tests selected, or effect/receipt transaction boundaries. A failure now leaves the schema atomically absent rather than partially initialized. Existing ARC evaluation revision hashing includes both modified modules, so old evaluation claims cannot silently resume under this implementation.

New regression tests inject a SQL exception after all schema DDL and verify rollback (and retry) for both constructors, preserving the preexisting governed schema on an ARC failure. A reopen test checks schema equality.

Validation: 57 targeted schema, governed-learning and ARC runtime tests passed in 2.175 seconds (Python 3.13). All 80 protected baseline path hashes still match. No model calls occurred.

Five real development workflow executions in fresh processes took 0.33035 seconds before and 0.26198 seconds after. The cProfile constructor cumulative time dropped from 0.146 to 0.073 seconds. These are single microprofile samples, with import and disk variability; they support the causal DDL improvement but are not evidence of fast-tier success. Reproduce with `python3.13 scripts/profile_schema_initialization.py <checkout-root>` while holding the shared test lock. JSON outputs and the targeted log are adjacent.

The external W0 full-profile report completed 2,803 tests, with failures in sandbox-dependent tests. Its current frozen fast subset alone accounts for 457.305 seconds excluding discovery/fixture overhead: 2,282 cases, 2,220 passing, 60 skipped and two loopback HTTP errors. The largest fast modules are compact dev study (59.03s), candidate v3 study (53.07s), world generalization (47.07s), ARC evaluation (41.73s), world model (15.93s), and substrate calibration (14.58s). Even removing the full measured ARC cost would leave over 415 seconds with other costs unchanged. This is an observed accounting bound, not a mathematical impossibility across future implementations.

The protected fast partition remains unchanged. A new tier partition cannot validly be frozen from this failed profile: the existing freeze operation requires a complete successful profile. Next action is a separately authorized successful profiling run with required sandbox capabilities, followed by human review of any proposed partition; or individually measured production improvements sufficient to close the remaining gap. No fast-tier pass is claimed.
