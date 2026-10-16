# V4 development verdict and final Sweden handoff

**V4 reached holdout_eligible on development: 839/900 correct versus adapted v1 at 581/900. No holdout was run and nothing was signed. All four pods are confirmed EXITED.**

This is a deterministic source-selection schema improvement in the adapted extraction pipeline. It is not a change to model weights, evidence of autonomous model learning, or a claim about clinician-verified real data. The registered candidate remained unchanged throughout this study.

## Development result

Each stratum contains 100 dev items. Intervals below are descriptive 95% Wilson intervals; they are not holdout evidence. The simultaneous adapted-v1 arm is shown, rather than substituting its earlier L4 stratum counts.

| Stratum | V4 correct | V4 interval | Adapted v1 correct |
|---|---:|---:|---:|
| conflict | 100/100 | 96.3–100.0% | 100/100 |
| dissenter | 100/100 | 96.3–100.0% | 100/100 |
| entity-decoy | 100/100 | 96.3–100.0% | 36/100 |
| format-variant-agreement | 68/100 | 58.3–76.3% | 49/100 |
| measurement-decoy | 100/100 | 96.3–100.0% | 35/100 |
| multi-source-agreement | 71/100 | 61.5–79.0% | 49/100 |
| stale-vs-current | 100/100 | 96.3–100.0% | 64/100 |
| supported-measurement | 100/100 | 96.3–100.0% | 48/100 |
| unit-mismatch | 100/100 | 96.3–100.0% | 100/100 |

Totals: v4 839/900 (93.22%), adapted v1 581/900 (64.56%), always-abstain 300/900 and random 136/900. The improvement was 258 correct answers, or 28.67 percentage points, with no stratum regression. There remain 61 wrong-provenance answers: 32 in format-variant agreement and 29 in multi-source agreement. Zero observed domain violations, invalid formats and false abstentions do not mean zero errors.

All 3,600 rows and 1,200 physical/model calls completed with zero timeouts. Study wall time was 3,021.795081 seconds; median request latency 1.6154 seconds and maximum 2.0442 seconds. Allocated dev compute estimate was $0.49524, separate from total setup/idle costs. Accuracy is measured on synthetic dev data; efficiency is reported above; robustness is unmeasured beyond this single seed; safety diagnostics are scoped to this harness; UX is n/a.

## Why holdout remains unused

The registered cumulative L6 allowance is 3,600 seconds. Development left 578.204919 seconds. The fresh calibration included a 62.352531-second cold load, yielding a 187.057592-second timeout and a required three-timeout reserve of 561.172777 seconds. Only 17.032141 seconds remained for dispatching holdout work after that reserve, insufficient for a complete slice. Root therefore did not register or run holdout. The verdict is development eligibility, not promote_proposal. No new skill or signature was created.

Root stage history and the final archive show no holdout registration, directory or calls. Restoration verified the original sealed bank and mode 000 private holdout files before study; the final backup excludes the separately preserved bank, so this handoff does not claim a fresh final remote permission-stat check.

## Runtime, budget and shutdown

Inference ran only on Sweden Secure A40 pod lvojhtouu5gede at $0.59/hour, qwen2.5-coder:7b digest `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`, served by Ollama 0.40.5. Fresh five-call calibration completed with zero timeouts before development. Total historical plus current physical attempts are 2,715, below 6,000. No laptop inference occurred.

Provider start was 2026-10-16T15:08:25.977Z. Root verified this pod EXITED at 16:12:56 UTC and all four pods EXITED by 16:12:57 UTC, before the 16:38:25.977 stop deadline. A pinned independent watchdog was armed and authenticated before setup; completion used STOP_NOW followed by provider readback. The exact stop-effect timestamp is unavailable, so accounting conservatively uses the confirmation time.

This Sweden interval is at most 3,870.023 seconds (1.075006 hours), approximately $0.634254 compute. Cumulative conservative running time is 19,467.934 seconds (5.407759 hours), approximately $3.190578 compute at $0.59/hour. Storage is excluded; these are estimates, not an invoice. The earlier Canada shutdown-verification delay remains recorded in document 103 and has not been erased.

## Preservation and validation

The final private archive is `/Users/aliyildirim/nerve-research-runs/sweden-20261016/resume-evidence.private.tar.gz`, mode 600, SHA `d82ff7929f9e174a28d4d2fe93fae8d30e9258a073c9fcd9bd405521883903ff`, 8,085,642 bytes. Private items remain outside Git. Public calibration/dev registrations, aggregates and sanitized EXITED receipts are versioned. Local replay completed successfully with network calls disabled: both new studies, historical L4 and calibration, all 2,715 contiguous physical claims, original claim hashes, registered sources, requests, row scores and final aggregates verified. The final replay receipt is evidence/sweden-final-offline-verification.json; its verification operation made zero model calls.

The existing retained skill-v1 record remains unchanged. Earlier CPU admission passed 2,226 tests with two dependency skips, and the new Sweden focused checks passed 6/6. The sequential gate remains unsigned/inactive: its earlier 200-proposal simulation accepted 0/40 harmful and 0/100 good proposals, so useful power failed despite 18.07% fewer consumed items. No learning claim is drawn from the earlier pre-written-handler 8/8 experiment.

The remaining research step is a prospectively registered, adequately budgeted conditional holdout evaluation of this exact frozen candidate. This run does not grant a new time window, pod allowance, promotion or signature.
