# Reproducible CPU benchmark and unavailable GPU gates

Run `PYTHONPATH=src python3 scripts/galahad_benchmark.py --samples 30`. The checked-in `evidence/cpu-benchmark.json` records actual local wall-clock measurements and the complete bounded research lineage. Environment: Python 3.10.0, macOS 26.5.2 x86_64. Eight approved synthetic records, fixed query/scope, limit 20, thirty sequential samples per arm. The same verified record content is returned by the direct-ledger and gateway arms.

| Arm | Records | Median ms | p95 ms | First call ms |
|---|---:|---:|---:|---:|
| No memory dispatch only | 0 | 0.000279 | 0.000332 | 0.001760 |
| Existing verified text retrieval | 8 | 0.555330 | 0.627358 | 0.629061 |
| Gateway with Null KV / ordinary text fallback | 8 | 4.134935 | 4.274634 | 4.217558 |

The gateway adds metadata serialization and fresh per-record authorisation/status checks; this local run shows overhead, not a speedup. No-memory is an explicitly unequal retrieval-capability control measuring empty dispatch only. There is no LLM in any arm. First-call timing is not proof of an OS/disk cold cache; subsequent medians are included separately. Timing arms run sequentially and are not a randomised inference study. Sample size and platform must accompany any quoted result.

GPU prefix-cache and Galahad restore arms, actual prefill/restore latency, time-to-first-token, token counts, GPU memory/energy, hardware disk throughput, ingestion/storage cost, concurrency, monetary cost and break-even are **null/unmeasured**. CPU byte fixtures cannot establish KV/logit equivalence. Restarting the SQLite ledger is not durable KV restoration. No conventional-cache/Galahad comparison is fabricated.

The separate existing v1.8 memory benchmark baseline is documented in `00-repository-audit.md`: its semantic arm is answer-keyed mock retrieval, not Mem0. This new experiment reuses the v1.9 inspectable public corpus and exposes that limitation; it is not blind ingestion or paper-scale anti-cheat reproduction.

Next hardware gate requires a compatible licensed Linux runtime, independently observed connector configuration, exact token/model identity, encrypted-store checks, cold/warm/restore/recompute separation, process-restart restoration, corruption and scope controls, random planted facts/decoys, and held-out answer keys. None of those GPU gates is represented as passing by CPU tests.

## Continuation: batched validation

`evidence/cpu-benchmark-cycle4.json` records 100 samples after batching authoritative revalidation into one bounded SQLite query. Existing ledger median 0.677586 ms; gateway median 1.500563 ms (p95 1.646569 ms). The earlier 30-sample gateway median was 4.134935 ms, but these sequential runs are not a controlled causal comparison. Gateway still has measurable overhead over direct ledger retrieval; no model inference or KV speedup is measured. Historical evidence is retained unchanged.
