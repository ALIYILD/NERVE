# Approved durations; both existing pods unavailable

The user approved L4 up to 3,600 seconds and cumulative L6 up to 3,600 seconds at 08:05:26 UTC on 16 October 2026. The approved amendment is active, but neither existing pod could restart. No dev study or conditional holdout has run.

Replacement `97vr620wnmtuga` returned HTTP 400 in start calls 243 (Galahad) and 161 (root). Original `lg0svvuenxvbno` returned the same error in root call 163: “There are not enough free GPUs on the host machine to start this pod.” Root's fresh readback at 08:20:23 UTC confirmed both EXITED. These failed starts added no running time or physical model attempts.

Cumulative conservative usage remains 3,937.034 running seconds and five physical attempts, with estimated compute cost $0.64524 excluding storage. The global limits remain six GPU hours and 6,000 physical attempts; inference ends by 10:15 UTC and final handoff by 10:30 UTC. No additional pod is authorized or created at this checkpoint.

The real bank remains sealed: 900 dev items, 300 holdout items, nine strata, manifest `5095941f6aa42b369bcd72dece08406ee87290ea7c56e71ca5e1017c738afa43`. No candidate was designed and no holdout slice consumed. The protected originals, calibration-pinned source and retained skill remain unchanged. Calibration replay verified exactly with network calls disabled.

The durable private archive remains `/Users/aliyildirim/nerve-research-runs/attended-20261016/nerve-attended-bank-v3.private.tar.gz`, SHA-256 `6b61fdc3cd68ca4d9ed45fb937b46765936e9e049827ce3133b4278ad8f921dc`. Full calibration receipts and all five shared physical-attempt claims remain in sibling `nerve-attended-calibration` and `nerve-attended-budget` directories. Restore these before any resumed study; do not regenerate the bank or reset the call budget. Private items remain outside Git.

The activation is recorded in `evidence/attended-duration-activation.json`; current state is in `evidence/attended-conductor-status.json`. A different pod identity would require a prospective versioned transport/calibration registration while preserving this bank and cumulative usage.
