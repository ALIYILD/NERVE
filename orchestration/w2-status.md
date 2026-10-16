# W2 status

- Inspected genuine historical dev receipts and ExperienceStoreV2 schema.
- Verdict: incomplete_infrastructure (execution preflight not authorized yet).
- Model calls: 0. Pod cost: $0. No holdout reads.
- Added immutable 100-item registration, fixed keep/revert scoring, deterministic
  failure-cluster proposal generation, and stable rejection-memory keys.
- D1 blocker: ExperienceStoreV2 only supports scientific_format_probe_v1 ordinals
  0–3. Bank-study ingestion requires a separately reviewed versioned schema; do
  not invent provenance or claim historical format episodes as fresh bank studies.
- D2 blocker: fresh 100-item experiments require usable pinned RunPod preflight,
  lock, frozen evaluator/controls, and a dev-bank allocation adapter.
- No candidate ready for holdout hand-off. No kept/reverted study claimed.
