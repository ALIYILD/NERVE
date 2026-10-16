# Bank v3: family-B generated and sealed

The real research bank was generated and independently validated, then sealed at **2026-10-16T06:42:37.542664Z**, before any candidate design or study inference. It contains **900 development and 300 holdout items across nine strata**. This is distinct from temporary unit-test fixtures.

Manifest SHA-256: `5095941f6aa42b369bcd72dece08406ee87290ea7c56e71ca5e1017c738afa43`. Generation-registration SHA-256: `689fdf6a9986722af2b8d087a2ead60cc769594f03bf21375659d09f88bd4acf`. Public metadata are `evidence/attended-bank-v3-{manifest,generation-registration,sealing-receipt}.json`. The registration was written before generation; the independent truth validator uses separate parsing/semantic code.

Each development stratum has 100 items. Holdout has 34 items for the first three strata and 33 for each remaining stratum. Three disjoint slices contain 100 items each, eleven per stratum plus one extra in a different one of the first three strata. Only slice1 may later be consumed under registered development eligibility; none has been consumed.

The nine strata are supported-measurement, measurement-decoy, entity-decoy, unit-mismatch, conflict, multi-source-agreement, stale-vs-current, format-variant-agreement and dissenter. The adapter preserves raw names, IDs, record order, stale records and qualified measurements. Comparisons are adapted pipelines, not unchanged retained skill v1.

On replacement pod `97vr620wnmtuga`, the bank lives at `/root/nerve-attended-bank-v3`. The seed, full holdout and three slices were verified mode000. This is a trusted-host filesystem boundary, not an independent enclave. The durable private local backup is `/Users/aliyildirim/nerve-research-runs/attended-20261016/nerve-attended-bank-v3.private.tar.gz`, mode0600 in a0700 parent. Its verified SHA-256 is `6b61fdc3cd68ca4d9ed45fb937b46765936e9e049827ce3133b4278ad8f921dc`. No private items are committed.

Runtime identity was separately verified: provider PID1 contains the pinned replacement podID (the SSH login shell omits it), NVIDIA A40, served Ollama0.40.5 and exact qwen2.5-coder:7b digest `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`. The stage launcher propagates only that verified provider identity into the unchanged transport guard. Receipt: `evidence/attended-runtime-identity.json`.

Calibration was registered for five public fixtures before calls. Its first execution approval was interrupted after305.2seconds without a process handle. A subsequent SCP audit found no consumed marker and zero physical attempt claims, so the study had **not started**. Registration and audit are preserved in `evidence/attended-calibration-registration.json` and `evidence/attended-calibration-launch-audit.json`. Root owns the next single launch. There is no efficacy result yet, and no candidate has been designed.

GPU accounting remains cumulative: original setup1160.783seconds plus all replacement running time since06:27:28.749UTC at$0.59/hour, including setup and approval waits. The replacement is still running at this checkpoint; final stopped time and cost belong in the final handoff.
