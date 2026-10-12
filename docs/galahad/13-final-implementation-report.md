# Final implementation report — 12 October 2026

**Latest orchestration:** [28-autonomous-research-campaign.md](28-autonomous-research-campaign.md) records the bounded campaign→trial→episode coordinator and overnight execution status. [29-registry-grounding.md](29-registry-grounding.md) records the scoped synthetic answer guard and fresh real-model validation. Neither is a claim of general autonomous discovery or weight training.

**Latest real-model study:** [27-real-model-evidence-study.md](27-real-model-evidence-study.md) records eight actual CPU-model completions, 3/4 relevant code-plus-citation matches and wrong-entity attribution in all four irrelevant controls. The full suite passed 1,182 tests; reliable grounding is not established. No training, policy promotion, deployment or real KV restoration.

**Latest successful local inference:** [26-cpu-research-inference.md](26-cpu-research-inference.md) records one accepted real CPU-model completion through the scoped gateway (72.684 seconds, 262 input/15 output tokens) and 1,173 passing tests. The new profile is host-only and opt-in; no deployment or broader accuracy claim.

**Latest runtime work:** [25-local-runtime-readiness.md](25-local-runtime-readiness.md) records safe inference diagnostics, two actual preload/probe attempts, a confirmed output-limit rejection, and 1,164 passing tests. No accepted local-model completion or deployment is claimed.

**Latest prospective study:** [24-online-adaptation-and-local-model.md](24-online-adaptation-and-local-model.md) records a +8.89-point online synthetic adaptation gain (84.33% versus 75.44%), 1,146 passing tests, and a failed real CPU-model smoke attempt. Candidate for review only; no default promotion or deployment.

**Latest research:** [23-discounted-feedback-research.md](23-discounted-feedback-research.md) adds opt-in per-observation discounting, a fresh v3 study and stricter experiment-arm validation. All six candidates failed at least one improvement gate; 5,800 actual synthetic tool calls were recorded, with the unchanged baseline at 148/200 heldout probes. No default promotion or deployment.

**Latest bounded loop:** [22-bounded-research-loop.md](22-bounded-research-loop.md) records 1,114 passing tests and 4,700 actual synthetic tool executions across two generations. No candidate passed all improvement gates; the current policy was retained (75/100 frozen holdout). No weight training or deployment.


**Latest self-study:** [21-nerve-self-improvement.md](21-nerve-self-improvement.md) documents the opt-in failure-tie fix, matched policy experiment and1,093 passing tests. Held-out selected/current accuracy tied73/100 with scenario regression, so the default was retained.

**Latest automatic adaptation:** [20-automatic-adaptation.md](20-automatic-adaptation.md) records the bounded automatic execution→evaluation→feedback path, durable budgets/replay claims and synthetic drift evidence. This does not complete the GPU or clinical gates.

**Latest learning continuation:** [19-outcome-learning.md](19-outcome-learning.md) documents executable, host-verified adaptive sessions and actual strategy changes across restart, with1,055 full-suite passes plus the final deletion-semantics regression.

**Latest continuation:** [18-hardening-report.md](18-hardening-report.md) records durable policy, optional inference and evidence-based operational readiness; [17-acceptance-matrix.md](17-acceptance-matrix.md) tracks the complete original specification. Older checkpoint details below are historical.

**Latest wiring checkpoint:** see [16-wiring-report.md](16-wiring-report.md) for the 992-test integration and [15-runtime-wiring.md](15-runtime-wiring.md) for executable commands. Existing agent and MCP source files are now modified as documented there.

**Continuation:** see [14-continuation-report.md](14-continuation-report.md) for the latest 951-test checkpoint, atomic quotas, concurrent API handling and one-use external holdout interface. The evidence below records the initial 926-test checkpoint; its single-host quota and request-lock limitations were subsequently addressed.

Status: partial master-plan implementation; locally verified CPU research checkpoint. No deployment, push, PR or merge. Real persistent KV restoration is not implemented or tested.

## Revision and workspace

- Worktree: /Users/aliyildirim/nerve-galahad
- Branch: feature/galahad-persistent-memory
- Baseline: ca1e2d92608654ab5d88c2a5866037656caf4a29
- Implementation checkpoint: 4e20333749656535aa7bcb877a3d8d083b463dab
- This report is committed separately; `git rev-parse HEAD` gives final documentation commit.
- PR: none created. Existing uncommitted work in other worktrees preserved.

## Delivered and reused

Added typed gateway contracts, scoped verified text retrieval, bounded context assembly, source integrity checks, pending proposals, host review, context-checked supersession/revocation/deletion, scope quotas and sanitised counters. Added optional metadata-only Galahad adapter, Null provider, canonical model/scope/prompt/token/source identity and non-activating preflight. Unknown runtime compatibility cannot enable restoration.

Added pinned-OIDC WSGI service, offline host grants, clinic/patient fixture matching, pending-only feedback, administrative checks, OpenAPI and HTTPS reference client. Tested real signed JWTs and actual loopback HTTP. No production IdP or Clinical OS application was connected. Inference endpoint returns 501; query returns evidence with review_required=true.

Reused MemoryAuthority, TrustedMemoryLedger, SecureMemoryRetriever, PinnedOIDCVerifier, RecursiveEvolutionLoop, RetrievalGenome, EvalScore and existing retrieval scorer. Preserved all existing source, agent, MCP, JEV, deployment and CI files. New CI workflow has not run remotely. Existing adaptive ranker remains injectable through the existing retriever.

## Validation evidence

Python 3.10.0 / Darwin x86_64. Existing CI target Python 3.12 Linux not newly executed here.

| Check | Result |
|---|---|
| Baseline full suite | 875 passed, 52.565 s |
| Final full suite | 926 passed, 53.385 s; zero failures/errors/skips |
| New gateway/provider/evaluation/API tests | 17 / 9 / 4 / 21 passed = 51 |
| Existing Node discovery | 7 passed |
| Existing smoke commands | 6 passed; exact commands in evidence/existing-checks.json |
| Syntax and whitespace | compileall and git diff --check passed |
| Dependency scan | four existing locked packages; no known vulnerabilities |
| Galahad preflight/readiness | exit 2, expected BLOCKED |

Initial sandbox full-suite run had 36 subtest failures and 3 errors from process isolation/loopback restrictions; approved permission-enabled baseline passed. New real HTTP fixture likewise required loopback binding permission. These failed runs were environmental and were not relabelled as successful.

## Measured CPU study

Thirty sequential local wall-clock samples, eight synthetic records, same query/scope/limit. Median existing ledger retrieval: 0.555331 ms; gateway + Null provider: 4.134935 ms. Empty no-memory dispatch: 0.000279 ms, explicitly unequal capability. First/subsequent and p95 measurements appear in evidence/cpu-benchmark.json. Gateway integrity/status rechecks add overhead. No inference speedup is claimed.

Existing bounded loop evaluated 12 data-only candidates over three generations, selected token/trigram weights 2/1. Constructed validation: 6/6 vs baseline 4/6; report-only holdout: 5/6 vs 4/6. Public fixtures are not sealed independent research evidence, and nothing was promoted. GPU memory/energy, prefill, TTFT, token costs, prefix cache comparisons and KV restore latency remain null/unmeasured.

## Security review and remaining limits

Independent reviewer reproduced and coordinator fixed: excessive advisory results; content corruption retaining false source provenance; legacy cross-context supersession. Regression tests cover each. Defined fixtures also cover tenant/agent/context denial, role intersection, expired/revoked authority, pending/rejected evidence, provider/ranker failures, failed invalidation, corrupt/missing stores and scoped quotas. No unresolved known leakage was observed in these fixtures; this is not a universal isolation proof.

The ledger remains plaintext research SQLite. Single-host quotas/rate limits are not distributed enforcement; trusted legacy writers can bypass gateway quotas. Provider invalidation failure is reported explicitly; backups/replicas and physical erasure are not verified. The WSGI process requires trusted ingress deadlines/TLS/connection limits. No prompt-injection immunity, sealed evaluation, audit sink/dashboard, or production encryption/key ownership is claimed.

## Blockers and proposed follow-up

This Mac has no installed Galahad/vLLM or verified GPU. Upstream compatibility/version and trust-domain guidance require reconciliation; licence rights, tenant-safe runtime identity binding, encrypted deletion and durable restart restoration require actual supported Linux infrastructure. No proprietary licence was accepted or service activated. Metadata checks are not a GPU smoke test.

Real connector deposit/restore, tensor/logit equivalence, kill/restart KV recovery, cache quotas/eviction, key mismatch/full-disk fault tests and matched inference controls remain BLOCKED. Independently sealed holdouts, broader policy candidates, automated existing-agent hooks, multi-process durable consent/revocation and operational dashboards remain future engineering, not completed features. No redundant unrestricted executor was created.

Clinical scope is synthetic-only. Live clinical governance, consent/auth integration, deployment/security assessments and formal approvals remain separate unresolved gates. No EPR writes, treatments, diagnoses or clinical recommendations were made.

## Exact reproduction

```sh
cd /Users/aliyildirim/nerve-galahad
python3 scripts/verify_galahad.py baseline
python3 scripts/verify_galahad.py cpu
python3 scripts/verify_galahad.py security
python3 scripts/verify_galahad.py faults
python3 scripts/verify_galahad.py api
PYTHONPATH=src python3 scripts/galahad_benchmark.py --samples 30
PYTHONPATH=src python3 scripts/galahad_preflight.py
python3 scripts/verify_galahad.py readiness
python3 -m compileall -q src/nerve_awim/memory_gateway scripts/verify_galahad.py
pip-audit --no-deps --disable-pip -r deploy/requirements-pilot-linux-x86_64.lock
node --test tests/test_checkpoint_discovery.cjs
git diff --check
```

Tests require the repository's existing PyJWT[crypto] dependency. Preflight and readiness deliberately exit 2; neither activates a runtime. Baseline/API tests need permission for temporary local servers and process-isolation fixtures. No special GPU command is supplied because no verified runnable restoration harness exists yet.

## Changed files

37 files added in the implementation checkpoint, plus this report. No existing files modified. Null provider and fault injectors are CPU fixtures; JWT/SQLite/HTTP are real local execution; KV and clinical deployment remain blocked/proposed.

- `.github/workflows/galahad-memory.yml`
- `docs/galahad/00-repository-audit.md`
- `docs/galahad/01-architecture.md`
- `docs/galahad/02-provider-compatibility.md`
- `docs/galahad/03-memory-gateway.md`
- `docs/galahad/04-retrieval-policy.md`
- `docs/galahad/05-agent-integration.md`
- `docs/galahad/06-recursive-optimisation.md`
- `docs/galahad/07-threat-model.md`
- `docs/galahad/08-benchmark-methodology.md`
- `docs/galahad/09-clinical-os-api.md`
- `docs/galahad/10-operations-runbook.md`
- `docs/galahad/11-clinical-safety-boundaries.md`
- `docs/galahad/12-release-readiness.md`
- `docs/galahad/evidence/cpu-benchmark.json`
- `docs/galahad/evidence/dependency-audit.json`
- `docs/galahad/evidence/existing-checks.json`
- `docs/galahad/evidence/preflight.json`
- `docs/galahad/evidence/validation.json`
- `docs/galahad/openapi.json`
- `scripts/galahad_benchmark.py`
- `scripts/galahad_preflight.py`
- `scripts/verify_galahad.py`
- `src/nerve_awim/memory_gateway/__init__.py`
- `src/nerve_awim/memory_gateway/client.py`
- `src/nerve_awim/memory_gateway/compatibility.py`
- `src/nerve_awim/memory_gateway/contracts.py`
- `src/nerve_awim/memory_gateway/evaluation.py`
- `src/nerve_awim/memory_gateway/galahad_adapter.py`
- `src/nerve_awim/memory_gateway/gateway.py`
- `src/nerve_awim/memory_gateway/kv_adapter.py`
- `src/nerve_awim/memory_gateway/null_kv_adapter.py`
- `src/nerve_awim/memory_gateway/service.py`
- `tests/test_galahad_provider.py`
- `tests/test_memory_gateway.py`
- `tests/test_memory_gateway_evaluation.py`
- `tests/test_memory_service.py`
