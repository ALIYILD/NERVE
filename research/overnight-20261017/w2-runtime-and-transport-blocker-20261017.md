# W2 CPU validation handoff — transport integrity and supported runtime

W0 remains the sole coordinator; inference is blocked by the failed latency preflight. This note does not authorize model calls or change any gate.

The W2 resume operator found an existing supported environment, without installing dependencies:

`/Users/aliyildirim/.cache/uv/archive-v0/OI2t9KVJQ6hSK7ic/bin/python`

It is CPython 3.13.12 and contains pytest and cryptography. The earlier 33-test result used Python 3.10 and cannot establish compatibility with the project's >=3.12 requirement. After the active W2 writer finishes changes, acquire the shared test lock atomically and rerun focused tests only under this supported environment. Include newly affected Hermes modules/tests. Register actual source hashes and the supported-interpreter test receipt; do not claim the older readiness applies to modified files.

At handoff, another writer is modifying `research/program-20261017.md`, `scripts/overnight_cycle.py`, `scripts/overnight_hermes_worker.py`, and `tests/test_overnight_cycle.py`, and adding `tests/test_overnight_hermes_claude.py`. This operator is not editing those files or testing moving sources.

Required transport correction: the current registration hashes the LOCAL worker file, but SSH executes a remote path without checking those actual bytes. Bind the executed bytes to the registered worker SHA-256 before execution. Prefer reading the remote worker bytes once, checking that hash, then compiling/executing those same bytes, avoiding a hash-check/execute race. Preserve the closed pod/worker binding and Linux pod identity, model digest, Ollama version and GPU checks. Add a focused mismatch test proving zero model calls on remote-byte drift. Neither a local file hash nor an earlier remote identity response proves later remote code identity.

Until source changes stabilize, supported-runtime validation and remote-byte integrity remain blockers. No model calls were made for this handoff.

## CPU resolution after c4e7501 stabilized

The remote launcher now reads the registered remote path once, verifies SHA-256 against the immutable session registration, then compiles and executes those exact bytes. Connection changes also fail against the registered binding. Focused tests include a changed-worker fixture whose dispatch marker remains absent on hash mismatch. Both remote workers' Linux identity guards remain unchanged.

All 41 focused tests passed on CPython 3.13.12 (cryptography 48.0.1), with an atomic test lock and identical before/after source hashes. Receipts: `cycle-remote-integrity-py313.json` and `.log`. These two CPU blockers are resolved for the recorded sources; live end-to-end behavior is unvalidated and the W0 latency-preflight block remains. No inference or pod calls were made.
