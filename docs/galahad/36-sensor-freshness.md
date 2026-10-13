# Freshness enforcement before observation recovery

The failure diagnosis exposed a prerequisite for any recovery experiment: historical sensor packets must not masquerade as current observations. The previous controller reset packet age on every accepted packet. Duplicate or out-of-order arrivals could therefore restore action eligibility during an outage.

`WorldCoreV2` now maintains a monotonic logical freshness clock. It reconciles elapsed action steps and explicit missing-packet ticks before deciding. Only a strictly newer observation timestamp can refresh the observation watermark, and that packet retains its logical age. Historical corrections still reach the existing lagged estimator. Invalid timestamps or measurements do not advance freshness. Boolean timestamps and boolean outage thresholds are rejected.

Regression tests cover repeated duplicates after an outage, duplicate arrivals interleaved with actions, newer historical packets after missed ticks, delayed first packets, historical estimate corrections, malformed packets, expiry without explicit `miss()` calls and continued operation with fresh observations. Independent review reproduced two bypasses in the initial patch; both were repaired before release.

This uses the simulator's logical action/missing-update clock, not physical wall-clock authentication. Supervised recovery now has an explicit `observe_recovery(timestamp, observed_now=..., position=..., velocity=...)` channel that advances while actions are suspended. Historical `ingest()` corrections cannot contribute recovery evidence. A host can advance time explicitly to expire pending evidence. Direct `choose()` and `act()` calls cannot bypass the approval phase.

The existing identity, signature, incident, evidence-consistency and nonce gates remain required. Approval requires the latest measurement to match the current trusted logical time and rechecks position/velocity bounds. Delayed records may contribute consistency evidence, but cannot seed a current state without an explicit dynamics model. Approval then seeds an estimator prior from the measured state without inserting a fictitious action. Calibration, forecasts and transition-deduplication state restart; configured and learned dynamics parameters are retained. A new timestamp epoch separates resumed observations from pre-outage packets.

The old recovery tests created several actions without sensors and counted historical observations as fresh recovery evidence. They now use the explicit channel and verify an actual action after authorized recovery, subsequent expiry, and denial through the existing authorization failure paths. This is an executable synthetic supervised-recovery flow; it does not establish physical safety, clinical readiness or autonomous permission to resume.

## Evidence and compatibility

The diagnostic protocol is now `worldcore-outage-diagnostic-v3`, with the inspected controller's new AST fingerprint. One actual mechanism-only replication completed 33 cases and 231 miss/choose pairs. No plant episodes or holdout calls ran. The existing outage search still cannot meet the absolute completion gate; this fix does not relax it.

The standalone `verify_supervised_recovery.py` run passed ten checks: initial stop, fresh samples, pre-approval lockout, invalid identity denial, authorized approval, no fabricated actions, actual resumed action, old-epoch rejection, later expiry and replay denial. Its identity provider is explicitly mocked; controller execution and the local signed-approval ledger are real research code.

The previous WorldCore receipt was explicitly checked and rejected against the new controller source manifest. Its historical evidence remains intact at commit `16c16b7`; it cannot authorize a current-source handoff. The earlier reproduction commands require their matching implementation revision and local ledgers. A new plant experiment requires a prospective protocol and unused final streams, not a source-hash bypass.

- [Executable synthetic recovery result](evidence/fresh-recovery-v1.json)
- [Current guard diagnostic](evidence/freshness-diagnostic-v3.json.gz)
- [Diagnostic summary](evidence/freshness-diagnostic-v3-summary.json)

## Verification

The final full repository suite passed **1,339 tests**, zero failures/errors, in 224.940 seconds. Earlier runs exposed recovery integration failures and a remaining legacy benchmark; those were repaired before this passing run. Independent review verified the corrected freshness, authorization and epoch behavior. See [validation evidence](evidence/freshness-recovery-validation.json).

## Reproduction

```sh
cd /Users/aliyildirim/nerve-galahad
.venv/bin/python scripts/verify_galahad.py baseline
PYTHONPATH=src .venv/bin/python scripts/verify_supervised_recovery.py --directory /private/tmp/nerve-fresh-recovery-replication
PYTHONPATH=src .venv/bin/python -c 'from nerve_awim.memory_gateway.worldcore_diagnostics import run_diagnostic; run_diagnostic("/private/tmp/nerve-freshness-replication")'
```

Use a new output directory. This public mechanism replication provides no new held-out evidence. The next research step remains a prospective plant evaluation of this supervised observation-recovery path; the stale-packet path is no longer an acceptable way to improve apparent completion.
