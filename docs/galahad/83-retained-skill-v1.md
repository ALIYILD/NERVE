# Loop 41 — v3@7B retained as skill v1

Under the user's explicit instruction “sign v3@7B”, Codex verified the original private dry and slice-2 receipts with the frozen canonical gate and retained the signed skill-v1 record. Zero inference was performed. This updates the operational status in historical doc 81 without changing its bytes or evidence.

`registry/scientific-v3-7b/registry.json` names v1 as current/retained and the exact evaluated compact-with-abstain@7B incumbent as superseded. The incumbent is explicitly a registry bootstrap, not an invented previous retained skill. Current pointer and supersession are published together by atomic replacement. Runtime activation and production authorization remain false.

## Signature and verification

A fresh local Ed25519 operator key was created under the user's explicit chat authorization. The trust record states authorized_by=user and executed_by=Codex; this is a delegated local signature, not a preexisting personal or hardware signature. The private key remains outside Git in a restricted user directory. The public trust document binds the exact skill, version, candidate configuration, predecessor, model digest, bank manifest and authorized payload. The adapter independently pins the trust document's hash in host code; replacing a key inside a candidate bundle cannot establish trust.

`load_selection_inputs` in `scripts/retained_scientific_skill.py` verifies registry metadata and supplies the pure retained-skill consumer with real signature and gate verifiers. Gate verification checks frozen source hashes, then invokes only the original canonical `verify` command on the preserved private dry and holdout journals. It compares their exact aggregates and requires `promote_proposal`. Missing evidence or invalid signatures fail closed.

Install the optional signature dependency with `python3 -m pip install -e '.[retention]'`. This archive is scoped to the original operator host: replay requires the frozen checkout `/Users/aliyildirim/nerve-runpod-evidence-frozen` and protected receipts under `/Users/aliyildirim/nerve-research-runs/runpod-slice2-20261015/private-receipt`. A public clone alone cannot replay private item evidence. Moving the host trust boundary requires a separately reviewed migration, not editing candidate-provided paths.

The one-shot historical signer refuses existing registry, trust or key state before mutation and is safe to import. It is not a general signing service; future signing requires new authorization.

## Evidence and interpretation

The decision is the sealed holdout verdict in [doc 81](81-runpod-slice2.md), commit 8194b2a: each of five strata 20/20, descriptive marginal Wilson 95% intervals 83.9–100%. Its registered count-based rule did not require a 90% or 95% lower confidence bound. The incumbent's output-format weakness limits interpretation to the complete pipeline, not a matched underlying-reasoning improvement. No development result was substituted for the holdout.

The original doc, registrations, aggregate receipts and verification evidence are preserved in Git. Item-level receipts remain gate-private in durable protected local storage. The worktree was moved out of /private/tmp to `/Users/aliyildirim/nerve-runpod-retention`.

Focused laptop CPU validation after recovery: 10 goal-orchestrator tests and 11 retention tests passed (including 5 actual asymmetric signature/trust checks and 6 separately labeled synthetic contract fixtures). The real-artifact consumer proof is documented separately with its receipt; fixture tests alone are not end-to-end evidence.

Runpod pod lg0svvuenxvbno remains stopped (EXITED); preserved storage can still bill. The retention operation uses zero model calls and has no GPU compute allocation. Original evaluation substrate: NVIDIA A40, qwen2.5-coder:7b, digest dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364; original dry/slice wall time and allocated cost are recorded in doc 81.

The separate persisted-handler result 8/8 versus 0/8 is **NOT evidence of learning or improvement**: a fixed best handler also scores 8/8. Tomorrow's adversarial bank v3 and clinician-verified cases were not run tonight.
