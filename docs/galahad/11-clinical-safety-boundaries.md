# Clinical safety boundaries

This integration is synthetic research only. Clinic and patient grant identifiers must begin with `synthetic-`; this convention is not a PHI detector and cannot make arbitrary caller text safe. Operators must supply only fabricated fixtures and must not connect EPRs, real patient databases or production clinical configurations.

Implemented outputs contain approved evidence, source IDs/content hashes and an explicit `review_required: true`. The service returns no generated clinical recommendation. Inference returns 501. Feedback creates a pending episode; only the existing trusted offline ledger evaluator can approve it. No automatic prescribing, diagnosis, treatment changes, device control, EPR write-back, patient communication or production promotion exists.

Authentication proves the configured issuer signed a token, and authorization intersects signed roles with exact offline grants. It does not verify a clinician's professional registration, consent or patient relationship; those production integrations remain missing. Context hashing is a namespace mechanism, not anonymisation or encryption.

Live use is blocked pending independent clinical safety and regulatory applicability assessment, including the user-specified UK GDPR, NHS DSPT, DTAC and DCB0129/DCB0160 requirements where applicable. This document records engineering boundaries, not a legal compliance determination. No such assessment, approval or deployed clinical integration has been completed.

Required future evidence includes accountable clinical ownership, consent and access policy, validated identity lifecycle, approved encryption and key custody, provenance review, stale-evidence handling, prospective workflow evaluation, secure deletion/backups, incident response and rollback. Existing NERVE deterministic gates remain authoritative and cannot be waived by memory hits, agent output, JEV review or a candidate optimisation score.
