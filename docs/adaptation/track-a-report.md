# Track A: branching synthetic benchmark

Ninety digest-frozen episodes cover heading correction, permitted fallback, contradiction review, restart, malicious source and scope isolation: 60 development and 30 held-out cases. The simulator executes new proposed actions through ARC; it is not fixed-trace replay. Fixed baseline, structured state without correction reuse and verified correction reuse share the same ARC/tool bounds.

| Split | Fixed baseline | State only | Verified corrections | Paired difference (95% interval) |
|---|---:|---:|---:|---|
| Development | 30/60 | 30/60 | 60/60 | 50.0 pp [38.3, 63.3] |
| Held-out | 15/30 | 15/30 | 30/30 | 50.0 pp [33.3, 66.7] |

Held-out p95 total episode overhead was 79.0% against the proposed 20% ceiling. Candidate adaptation-v1 was rejected. Timing includes local SQLite/engine setup and reauthentication; it is not isolated provider or generation latency. The overhead measure is a conservative engineering signal, not a production performance prediction.

The fixed planner cannot retain a corrected heading/fallback, so gains partly follow directly from feature availability. Public template-related synthetic episodes are not independent clinical validation; the bootstrap interval does not resolve that limitation. Per-family denominators and every episode result are in the JSON reports.

After held-out consumption, final review added an explicit-parent replan guard and durable budget termination. The recorded frozen report retains its original code digest and is not current-code held-out evidence. Final code was rechecked on development cases and targeted adversarial tests only. Do not reuse this held-out batch for a revised candidate; the next benefit evaluation needs a fresh independent batch and new candidate. This preserves the failed attempt rather than replacing it with selectively rerun results.
