# Claude CLI master implementation prompt

Run Claude Code from the NERVE repository root and paste the following prompt. It delegates implementation, not permission to fabricate benchmark results or bypass existing host approval.

```text
Implement the NERVE Cognitive Cue Engine described in docs/cce/implementation-plan.md.
Read docs/cce/architecture.md and docs/cce/reproduction.md first. If those files
are unavailable, reconstruct them from current source and the cited primary
sources before coding. Treat the fifteen loop gates as the acceptance criteria.

You are the integration coordinator. Use available subagents for parallel
research/documentation, engine implementation and independent evaluation work.
Give each worker a disjoint file scope or isolated worktree, explicit contracts,
and a requirement to return actual evidence. You alone integrate verified work.
Inspect AGENTS.md, git status and existing changes first. Preserve unrelated work.

Extend existing NERVE interfaces. Reuse HermesAgentRuntime, the trusted memory
ledger, governed registered strategies, bounded learning, and existing canary/
promotion controls where their actual contracts apply. Do not build a competing
agent scheduler, memory authority, release controller or unauthenticated API.
The numeric simulation coordinator and narrow repository/evidence-handoff hosts
are not general LLM inference systems; do not claim unsupported connections.

Implement typed, bounded cue registry/provenance and model/tokenizer/template
profiles, candidate discovery, paired independent evaluation, compatible routing,
advisory JEV integration, scoped memory feedback, bounded recursive improvement,
local API/CLI/reporting, tests and operational documentation. Preserve exact cue
bytes and actual tokenizer identities. Distinguish native assistant prefill from
instruction prompting. Unsupported provider features return no-cue fallback.
Keep default behavior disabled and retain a first-class no-cue baseline.

Clinical and high-risk requests must not acquire experimental cues through this
research feature. Never bypass clinical controls, provider restrictions, host
permissions or clinician approval. Agents can propose but cannot grant authority.
Use public/synthetic data; keep secrets, patient data and raw private outputs out
of logs and external reviewers. Existing host/operator authorization is binding.

Use paper arXiv:2610.06851v1 and author repository github.com/sophicle/cues as
primary research references. Record the paper/code proposal-count discrepancy.
Pin all experiment dependencies and identities. Do not claim the paper is
reproduced by deterministic fixtures, a five-task demo or incomplete samples.
Do not infer benefit on a hosted/chat/clinical model from base-model results.

Discovery must not see final answers. Freeze candidate selection before opening
the final holdout; detect duplicate content across splits and preserve one-time
holdout use across resumes. Use independent host graders, count failures in
denominators, report uncertainty and unknown costs honestly, and keep answer
agreement separate from correctness/calibration. JEV is advisory only.

For EACH loop: implement, run meaningful targeted tests, inspect failures, repair,
retest, and record artifacts/commands/exit status for its completion gate. Complete
independent work even when another loop needs external resources. Run the full
repository unittest suite with PYTHONPATH=src after integration, plus applicable
existing CI checks. Never report a command as passed unless you observed success.

Use bounded budgets and explicit host-configured live execution. Do not acquire
paid infrastructure, send third-party messages, activate scheduled jobs or modify
external production systems without applicable authorization. When a required GPU,
model, credential, endpoint, staging target or clinical approval is unavailable,
document the precise blocker and the prepared next command/artifact; leave that
gate open while completing all feasible software work. Do not ask repeatedly for
authorization already present, and do not invent deployments or approvals.

Deliver a reviewable diff, complete fifteen-loop evidence/status table, architecture
map, reproducibility manifests/protocol, tested local usage, observed test results,
known limitations and staging/rollback handoff. Distinguish implemented, locally
verified, externally reproduced and deployed. Continue until every feasible item
is complete and every remaining gate has a concrete documented blocker.
```

The prompt intentionally separates software completion from empirical results and external deployment. A coordinator can finish the reviewable implementation while leaving the paper-reproduction and clinical/staging gates open with precise evidence requirements.
