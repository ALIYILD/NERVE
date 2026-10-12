# Continued implementation — CPU reliability and evaluation

Branch: `feature/galahad-persistent-memory`. Starting checkpoint: `0507f7aae5a157565b1260e5b5807dd105ea136b`. This report accompanies the next local commit; `git log -1 --format=%H` identifies it. No push, PR, deployment or clinical activation.

## What changed

- **Atomic persisted scope quotas:** opt-in SQLite policy and insert/scope-move triggers enforce limits inside the existing ledger transaction. Covers independent gateway instances and legacy writers. Conflicting restart configuration fails; existing excess records remain available for read/delete. The quota policy applies only to the chosen ledger; no production database was used.
- **Batch revalidation:** materialise bounded advisory IDs before one fresh scoped SQLite snapshot. Preserves output order, approval, expiry, provenance checksum and count/character budgets. Added a lazy-ranker revocation regression. Revocations after the snapshot may overlap an in-flight response; delivered text cannot be recalled.
- **Concurrent API requests:** removed request-wide lock from client reads/JWT/gateway calls. Rate accounting remains atomic. Capability and expiry rechecked after body reads. Stalled-upload, concurrent rate-limit and revocation-during-upload tests pass. Hosting still needs multiple workers, ingress deadlines and TLS.
- **External holdout interface:** separate freeze and evaluate CLI operations bind typed selected/baseline candidates, scope and external dataset digest to a durable one-use claim. Consumed claims survive restart and fail closed after errors. Evaluation accepts no candidate overrides and sends both candidates the same approved gateway record set. The answer artifact stays external. This is not malicious-host protection or cryptographic secrecy; no independently governed experiment was performed.
- **Crash recovery:** killed a real subprocess after an uncommitted synthetic SQLite insert. Reopening rolled back the record and preserved quota capacity. This is semantic-ledger recovery, not KV restart restoration.

Reused the existing ledger, authority, scorer, RetrievalGenome and gateway. No new model, executor, shell capability or deployment path.

## Validation

Full suite: **951 passed in 44.607 seconds**, zero failures/errors/skips; previous checkpoint 926, therefore 25 additional tests. New-package suites total 76: gateway18, provider9, evaluation4, service/client25, lifecycle8, holdout12. Syntax compilation and whitespace checks passed. Tests used real temporary SQLite stores, subprocesses, JWT signatures and loopback HTTP; provider fault fixtures remain synthetic. A final bounded-startup-wait adjustment in the subprocess test was independently rerun: lifecycle8/8 passed.

Four concurrently released writer processes attempted 32 writes at quota5: **5 admitted / 27 rejected**. Two writers used the gateway, two the direct legacy ledger. Restart, direct writes, scope-changing SQL, conflicting configuration, missing policy and crash rollback fixtures also passed.

Independent review repaired a holdout scope bug: an authorised actor in scopeB could otherwise consume scopeA's claim before mismatch rejection. Wrong-scope denial now preserves the claim for the rightful scope. CLI candidate overrides are rejected rather than silently ignored.

## CPU measurement

`evidence/cpu-benchmark-cycle4.json`: 100 sequential samples, eight synthetic records, same query/scope/limit. Median direct ledger **0.677586 ms**, gateway **1.500563 ms**, gateway p95 **1.646569 ms**. Earlier historical gateway median was 4.134935 ms on a separate 30-sample run. These were not simultaneous controlled measurements; no causal speedup percentage is asserted. Gateway overhead remains above direct retrieval. No LLM prefill, KV, token-cost or GPU-energy measurements.

## Remaining gates

Real Galahad connector execution, verified GPU/runtime/licence, durable KV restart, runtime keying/isolation, encryption and deletion remain blocked as documented previously. No clinical inference, live patient data or Clinical OS deployment. The service still lacks durable distributed identity/consent revocation and rate limiting. Approved ledger storage is plaintext. Scope quotas do not bound the total number of operator-configured scopes or encrypt storage. External holdout custody is an operator obligation; replacing its database or reading answers defeats methodological isolation. Broad policy search, operational dashboards and live agent hooks remain future work.

## Reproduce

```sh
cd /Users/aliyildirim/nerve-galahad
python3 scripts/verify_galahad.py baseline
python3 scripts/verify_galahad.py cpu
python3 scripts/verify_galahad.py security
python3 scripts/verify_galahad.py faults
PYTHONPATH=src python3 scripts/galahad_benchmark.py --samples 100
PYTHONPATH=src python3 -m unittest discover -s tests -p test_memory_holdout.py -v
PYTHONPATH=src python3 scripts/galahad_holdout.py --help
PYTHONPATH=src python3 scripts/galahad_preflight.py
```

The API/full suite needs permission to bind temporary localhost servers. Preflight still exits2 intentionally. Actual external holdout digest/freeze/evaluate commands and strict artifact format are documented in `06-recursive-optimisation.md`; use protected external synthetic fixtures and never commit answer keys.

## Files

Added: `memory_gateway/lifecycle.py`, `memory_gateway/holdout.py`, `scripts/galahad_holdout.py`, `tests/test_memory_lifecycle.py`, `tests/test_memory_holdout.py`, new benchmark/validation evidence and this report.

Modified: `memory_gateway/gateway.py`, `memory_gateway/service.py`, gateway/service tests, `scripts/verify_galahad.py` and Galahad architecture/gateway/evaluation/threat/benchmark/API/runbook/readiness/report documentation. Existing pre-gateway NERVE source modules and production configurations remain unchanged.
