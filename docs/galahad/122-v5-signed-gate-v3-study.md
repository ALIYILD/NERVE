# V5 versus retained family-B v4 under signed gate v3

The user corrected the nonexistent doc94 twenty-item calibration. No such fixture was created. Admission instead required the existing five-call Runpod latency/identity check and replay of the first ten candidate rows in doc106's registered dev schedule. All holdouts stayed sealed through these checks.

Original Sweden pod `lvojhtouu5gede` could not start: Runpod reported no free GPUs on its host. It remained EXITED. The existing final-holdout Sweden A40 `5xndo7i7s5r9zn` was resumed at $0.59/hour. Runtime identity matched NVIDIA A40, Ollama 0.40.5 and qwen2.5-coder:7b digest `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`. The cached runtime was restored; no model substitution or local inference occurred.

The historical input and schedule hashes verified before requests were issued. The first five latency calls took 13.757769, 1.717770, 1.633851, 1.897719 and 1.559792 seconds, within the registered historical observed band [1.523075, 62.352531] seconds. There were zero timeouts. The first ten candidate dev rows required seven model calls and three deterministic abstentions; all ten decoded records matched the recorded canonical JSON bytes exactly. A separate fresh-process offline replay verified these results with networking disabled and zero additional model calls. Request/response journals remain private under `/Users/aliyildirim/nerve-research-runs/v5-identity-replay-20261016`.

The study registration is [v5-gate-v3-study-registration.json](evidence/v5-gate-v3-study-registration.json), SHA256 `f12a178767efc14a649a9bd265d1027f1f9578b88a281ec3fd8b5afc023b752f`. It binds seed 2026101804, incumbent decoding seed 20261016, the frozen doc113 candidate, signed canonical gate v3 (43c3e78), m=10, t=0, total cap500, primary cap100, main cap460 and unconditional N=40 dissenter follow-up after primary acceptance. It supersedes only doc113's old evaluation protocol; the deterministic numeric-agreement/smallest-source rule is unchanged.

Always-abstain and random are hard gates: at the completed study, candidate correctness must equal or exceed each control in every observed stratum and strictly exceed each overall. Domain violations prevent promotion. These controls do not create an early-prefix veto. Gate thresholds, coverage requirements and futility rules are unchanged. Source hashes were checked once at study admission, not per item; concurrency is one request, below the four-request limit. Timeouts use three times the measured calibration maximum with two identical-request retries only on timeout, each journaled.

Bank v4 manifest `8ae1b71b421fe8ace9b89dff0bcc359c79b7d535960306e0640da76fdba79aeb` was verified. A private exclusive allocation was recorded before outcomes; each stratum uses a seed-hashed order of reserve indices, sampled without replacement. The custodian restores reserve files to mode000 after loading its allocation. Unused allocated items remain quarantined, not silently released for reuse. No other bank or holdout was opened. V5 adds zero model calls; only the retained v4 comparator needs remote inference. Public results contain counts and a trajectory without item identifiers or outputs.

The e-process's type-I guarantee depends on its registered conditional-null assumptions. This is a fresh sealed synthetic-bank comparison, not evidence about clinician-verified real cases. No candidate signing, retention or external messaging is authorized by this study.



Verdict: **insufficient_power**, reason `primary_cap_without_acceptance`. V5 scored100/100, incumbent v4 scored92/100: eight wins, zero losses and92 ties. Both hard controls passed (always-abstain33/100; random15/100), with no domain violations. The final e-value was **8.15730721**, below20 at the primary100 cap. Coverage sampling and the N40 follow-up were not entered. This is not a promotion or a retain-incumbent statistical verdict. The incumbent remains in place because no promotion was authorized. The observed tie rate was92%, higher than the75% simulation fixture; there were too few discordances to reach the registered threshold. No threshold was changed and no additional holdout was run.

| Stratum | Items | v5 | v4 | Always-abstain | Random | Wins | Losses | Ties |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| conflict | 11 | 11 | 11 | 11 | 4 | 0 | 0 | 11 |
| dissenter | 11 | 11 | 11 | 11 | 5 | 0 | 0 | 11 |
| entity-decoy | 11 | 11 | 11 | 0 | 1 | 0 | 0 | 11 |
| format-variant-agreement | 11 | 11 | 7 | 0 | 0 | 4 | 0 | 7 |
| measurement-decoy | 11 | 11 | 11 | 0 | 0 | 0 | 0 | 11 |
| multi-source-agreement | 11 | 11 | 7 | 0 | 1 | 4 | 0 | 7 |
| stale-vs-current | 11 | 11 | 11 | 0 | 0 | 0 | 0 | 11 |
| supported-measurement | 12 | 12 | 12 | 0 | 0 | 0 | 0 | 12 |
| unit-mismatch | 11 | 11 | 11 | 11 | 4 | 0 | 0 | 11 |

The complete aggregate and per-observation e-process state, without item identifiers, are in [result](evidence/v5-gate-v3-result.json) and [trajectory CSV](evidence/v5-gate-v3-trajectory.csv). E-values at 10, 20, 40, 50, 60, 80, 90 and 100 items were 1.30, 2.197, 2.197, 2.8561, 4.826809, 6.274852, 8.157307 and 8.157307 respectively.

Fresh-process replay verified all 100 scored rows, request-body bindings, response decoding and the canonical aggregate bytes, with network access disabled and **zero repeated inference**. Aggregate SHA256: `ab3d0fac8a2a1af8745c6622b9a919432ef93adc09569f40386050d295f9e385`. The [offline replay receipt](evidence/v5-gate-v3-offline-replay.json) records this check. Seven candidate unit tests and nine separate CPU scorer fixtures passed. Private request, response, item and score journals remain outside Git; public hash indexes commit to their contents.

The study used 67 remote calls, zero timeouts, 117.743 seconds of measured remote call time and 210.338 seconds wall time. The preflight added 12 calls, making 79 model calls total. No inference ran on the laptop. Pod `5xndo7i7s5r9zn` was stopped immediately after the study and independently read back as **EXITED**; the unsuccessful original pod `lvojhtouu5gede` also remained EXITED. The full running interval, including setup, approval waits and registration, was 26.278 minutes (0.438 GPU hours), about **$0.26 estimated compute** at $0.59/hour, not an invoice. Preserved storage is excluded. See [shutdown](evidence/v5-pod-exited-receipt.json) and [cost/time receipt](evidence/v5-pod-cost-and-wall-time.json).

Bank v4 has 100 consumed reserve items. The exclusive admission allocated 508 potential slots (52 per stratum plus 40 additional dissenter slots); its 408 unused allocated items remain quarantined. There are 1,292 unallocated reserve items. The 500-item observation cap was never exceeded. All nine reserve files are again mode000. The [consumption summary](evidence/v5-gate-v3-consumption-summary.json) binds the private ledger; no unused slots were released or reused.

No signing, retention, protected gate changes or external messages occurred. This completed study does not authorize another run.

Post-study signature, policy and protected-source verification passed ([receipt](evidence/v5-post-study-gate-integrity.json)). The historical `check_signed_promotion_gate_v3.py` smoke test asserts that bank v4 is completely unconsumed; that specific precondition now fails because this authorized study consumed 100 items. It passed before the study. The old check and all protected sources were left unchanged; the post-study check instead verifies the signed gate and the completed 100-item allocation.
