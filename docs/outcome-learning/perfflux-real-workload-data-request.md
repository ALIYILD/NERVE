# PerfFlux real-workload data request

**For:** David / Swapnil, PerfFlux team. **Purpose:** bind NERVE's first
non-synthetic offline workload goal to measured batch timings and independently
checked correctness. Please supply existing authorized measurements or safe
offline replays; this request does not authorize production experiments.

**Format and delivery.** UTF-8 `runs.jsonl`, one actual batch execution attempt
per line, including failures, timeouts and retries; `manifest.json` with schema
version, export owner, collection dates, permitted use, units, file SHA-256,
row counts and missing-field definitions; short `README.md` describing collection
and timing boundaries. Use UTC timestamps and numeric milliseconds. Supply via
the team's approved private channel. Do not include customer payloads.

**Required fields per attempt:**

| Group | Fields |
| --- | --- |
| Identity / ordering | Pseudonymous `run_id`, `batch_id`, `pair_id` (if paired), `workload_id`, `session_id`; timestamp, sequence, retry index |
| Workload | Batch item count, input byte count, input-size distribution summary, workload class; duplicate fraction and cache state when measured |
| Environment | CPU/GPU model and count, memory capacity, software/build version, concurrency, warm/cold flag; opaque environment ID |
| Strategy | Incumbent/candidate identifier, immutable strategy/config hash; selection method (randomized, interleaved or observational) |
| Measurement | Queue, execution and end-to-end duration in ms; timing method and boundaries; timeout limit, completion status and error class |
| Correctness | `pass`, `fail` or `unknown`; independent verifier/version or reviewer ID, opaque evidence reference, output digest where useful |
| Optional measured cost | CPU/GPU time, peak memory, energy or billed cost with units and measurement method; null if unavailable |

**Labels and comparison.** Correctness must come from an independent reference
or domain review, never from runtime alone or NERVE's own prediction. Explain
tolerance rules and missing labels; retain `unknown` values without guessing.
Where available, pair incumbent and candidate on the same input batch and
environment, randomizing or interleaving order and recording cache/warm-up
conditions. Export both timings. Observational logs are acceptable for intake
but cannot by themselves establish causal savings. Digests alone do not prove
correctness without a reference. Include failures to prevent survivorship bias.

**Volume and partitioning.** Pilot request: at least 300 matched pairs spanning
three workload conditions and three independent sessions. If unavailable,
50 pairs can validate ingestion only, without an improvement claim. This is a
collection target, not a power guarantee. Agree chronological development and
sealed evaluation partitions before scoring; propose 70/30 with batch-family
separation. Deliver development first, retain sealed data separately with its
owner until explicitly authorized. Record partition counts and leakage controls.
NERVE will freeze the manifest and preregister a latency target (for example
paired p95 end-to-end latency), correctness/error constraints, budgets and
uncertainty analysis before candidate evaluation. No target is fitted to sealed
results. The goal remains unbound until real data and labels pass intake review.

**De-identification.** Remove PHI, personal/customer identifiers, prompts, raw
inputs/outputs, credentials, hostnames and IPs. Use stable export-local opaque IDs
or keyed pseudonyms; retain keys internally. Generalize identifying workload
metadata. If timestamps require shifting, preserve ordering and durations and
document the shift policy. Confirm permission to share, retention period and
deletion contact. David/Swapnil must supply actual measurements: synthetic
timings or guessed labels cannot satisfy this request.
