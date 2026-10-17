# Fast-tier continuation diagnosis

The original exclusive run timed out at 180 seconds during the first ARC evaluation test, after the preceding alphabetically ordered test modules. A separate original ARC evaluation probe was killed after 60.153 seconds. These observations identify a hotspot, not a passing gate.

The frozen manifest has `new_modules_default=fast`: the recorded discovery diagnostic counts 2,282 fast tests versus 2,044 total tests at the manifest's original measurement. ARC evaluation is one of the new modules. Changing the protected partition or increasing the fast deadline is outside this continuation.

`arc_evaluation._run_benchmark` executes 30 development episodes, 90 validation episodes across three candidates, and 180 three-arm benchmark episodes: 300 separate workflow stores for one test. Every workflow creates a GovernedLearning schema (seven tables) and ARC schema (five tables and one trigger). Previously these 13 DDL statements each ran in SQLite autocommit: a connection's Python context manager does not begin a transaction for `executescript`.

The proposed patch starts a transaction inside each of these two schema scripts. The existing `_db` context commits on success and rolls back on exception. This reduces schema commit boundaries from 13 to two per workflow, without changing SQLite synchronization, stored schema, evaluator settings, tests selected, or effect/receipt transaction boundaries. A failure now leaves the schema atomically absent rather than partially initialized. Existing ARC evaluation revision hashing includes both modified modules, so old evaluation claims cannot silently resume under this implementation.

New regression tests inject a SQL exception after all schema DDL and verify rollback (and retry) for both constructors, preserving the preexisting governed schema on an ARC failure. A reopen test checks schema equality.

Validation pending the shared test lock held by another W0 continuation's full profile. No speedup or fast-tier success is claimed at this point.
