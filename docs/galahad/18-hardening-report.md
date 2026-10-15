# Durable policy, inference and operational completion checkpoint

12 October 2026. Branch `feature/galahad-persistent-memory`. This extends checkpoint `6ce176e7812e66f18f3fe71cd628b78e7073a1f3`; final code revision and validation appear in the evidence section below. No push, PR, merge or deployment was performed.

## Executable additions

- Persistent exact-scope revocation and deletion use the authoritative SQLite ledger. Tombstones survive restart and block legacy inserts/approvals; a revoked configured session can be constructed for host startup but every read/proposal/health operation remains denied. Administrative cleanup remains possible.
- Scope and source lifecycle audit contains allowlisted events, timestamps and random trace IDs. Export excludes payloads, patient identifiers and source IDs. The local audit window is bounded to10,000 rows; tombstones remain retained.
- Optional host-configured loopback inference connects `/v1/inference/respond` to `/v1/chat/completions`. It sends only approved evidence, abstains without evidence, checks exact model/response shape, forbids tool calls, bounds output and four concurrent calls, and circuit-breaks repeated failures without retry. Permissions, evidence and JWT are checked again after network work. Model output remains untrusted and review-required. Socket inactivity timeout is not a hard total deadline against a trickling server.
- Administrative scoped revoke/delete routes and OpenAPI schemas are wired to durable policy. Existing identity/grant checks remain mandatory. Omitted inference configuration preserves the unavailable response.
- Operational commands run actual CPU/security/API suites and temporary fault scenarios. Readiness requires fresh manifests matching both Git revision and source fingerprint. Label-free Prometheus output and reference alert rules are supplied; no monitoring service is deployed.
- Passive runtime observation tooling captures actual HTTP latency, reported tokens, output fingerprints and optional metrics from an operator-owned endpoint. Its loopback transport tests use synthetic responses. It cannot certify tensor restore, Galahad attribution or complete worker restart.

Existing v1.8 verified ledger/retriever, adaptive utility scorer, host capability/OIDC boundary, v1.9 bounded evolution, registered demo agents, parallel workers and official MCP transport remain the reused foundations. No new unrestricted executor was introduced.

## Review and limits

Independent review identified non-atomic source audit, legacy deletion utility residue and policy reads recreating a missing file. Fixes and regression results are recorded with the validation evidence. Historical orphan utility rows from deletions before the cleanup trigger cannot be assigned a deleted context safely; they require a separately governed retention migration. Restoring an old backup can resurrect deleted data or remove tombstones: reconcile current revocations before reuse.

The research ledger is plaintext. Physical erasure, encrypted storage/key rotation, backup destruction, distributed consent, full-disk/runtime fault execution and production ingress are not certified. Clinical use remains prohibited by the project's stated boundary. General clinical contradiction resolution, wider optimisation candidate families and an actual DeepSynaps application connection remain incomplete; the acceptance matrix lists these explicitly.

Galahad preflight on this Mac reports unsupported platform, no installed Galahad/vLLM, no verified NVIDIA hardware/licence/runtime matrix, no proven identity/trust-domain isolation or encrypted deletion, and no implemented real runtime connector. An approved Linux GPU workspace and verified licence rights are required before that work can be executed. No licence was accepted or paid resource acquired. Synthetic HTTP tests are not actual model inference. Nothing here is a live clinical workflow.

## Reproduction

From `/Users/aliyildirim/nerve-galahad`, using the repository's synthetic dependencies:

```sh
.venv/bin/python scripts/verify_galahad.py baseline
PYTHONPATH=src .venv/bin/python scripts/memory_gateway_demo.py
PYTHONPATH=src .venv/bin/python scripts/memory_gateway_demo.py --provider galahad
PYTHONPATH=src .venv/bin/python scripts/memory_gateway_mcp_wire.py
PYTHONPATH=src .venv/bin/python scripts/memory_operations.py verify --gate cpu --output /tmp/nerve-cpu.json
PYTHONPATH=src .venv/bin/python scripts/memory_operations.py verify --gate security --output /tmp/nerve-security.json
PYTHONPATH=src .venv/bin/python scripts/memory_operations.py verify --gate api --output /tmp/nerve-api.json
PYTHONPATH=src .venv/bin/python scripts/memory_operations.py faults --output /tmp/nerve-faults.json
.venv/bin/python scripts/verify_galahad.py readiness --evidence /tmp/nerve-cpu.json /tmp/nerve-security.json /tmp/nerve-api.json /tmp/nerve-faults.json
PYTHONPATH=src .venv/bin/python scripts/galahad_benchmark.py --samples 100
PYTHONPATH=src .venv/bin/python scripts/galahad_preflight.py
.venv/bin/python scripts/galahad_gpu_smoke.py --help
```

Preflight exits2 for the blocked real provider. Readiness exit0 means only the defined CPU research gates passed. Run manifests after checkout/source changes stop; a later commit invalidates revision-bound manifests, even for a documentation change. Full-suite tests require local HTTP/process-isolation permissions. Real probe commands and evidence limitations are in [the acceptance matrix](17-acceptance-matrix.md).

## Evidence

Code commit: `5802bb8372f9355ad4f5cb99fa305600c2bbaa4a`. The following documentation-only commit does not change executable source; its SHA is available through `git rev-parse HEAD`. The evidence remains explicitly bound to the code commit, so rerun the manifests on the final checkout before using readiness operationally.

- Full suite: **1,038 passed**, zero failures/errors/skips,54.909seconds on Python3.10.0/Darwin x86_64.
- CPU163, security159, API58 tests passed; these groups overlap and must not be added to the full-suite count. Five synthetic fault checks passed. Readiness returned `cpu_research_ready=true` for the matching code revision/source.
- Both actual signed-HTTP demos passed; official MCP2.3.0 stdio passed. Inference18 tests use a synthetic HTTP responder, not a model/GPU. Policy13 tests include all three review regressions. Operations8 tests include refusal of skipped required suites.
- `git diff --check`, compileall and `pip check` passed. New remote CI workflow steps are committed but have not run remotely. Previous dependency audit scope/limitations remain in the earlier report.
- The initial sandboxed regression attempt failed process/loopback permission fixtures; an authorised run passed1,032 tests, followed by the final1,038-test run after repairs. Environmental failures were not counted as passes.

Benchmark after regression processes completed:100 sequential calls per arm with eight synthetic records, same query/scope/limit, macOS26.5.2 x86_64/Python3.10.0. Existing ledger median0.537056ms (p95=0.592301); gateway+Null median2.833880ms (p95=3.008439). First calls0.589784ms and2.994994ms are not guaranteed cold OS cache. Empty dispatch0.000215ms has no retrieval capability. The gateway adds CPU overhead; no model-inference speedup/cost saving is claimed. The public bounded research fixture evaluated12 candidates in3 generations and remains unsealed/report-only; no candidate deployed.

Evidence: [validation](evidence/hardening-validation.json), [benchmark](evidence/hardening-benchmark.json), and `evidence/hardening-{cpu,security,api,faults}.json`.

## Files in this continuation

Added/modified code and documentation in commit `5802bb8`:


```text
M	.github/workflows/galahad-memory.yml
A	deploy/memory-alerts.yml
M	deploy/requirements-memory-synthetic.txt
M	docs/galahad/09-clinical-os-api.md
M	docs/galahad/10-operations-runbook.md
A	docs/galahad/17-acceptance-matrix.md
M	docs/galahad/openapi.json
A	scripts/galahad_gpu_smoke.py
A	scripts/memory_operations.py
M	scripts/verify_galahad.py
M	src/nerve_awim/adaptive_memory.py
M	src/nerve_awim/memory_gateway/gateway.py
A	src/nerve_awim/memory_gateway/inference.py
A	src/nerve_awim/memory_gateway/observability.py
A	src/nerve_awim/memory_gateway/policy.py
M	src/nerve_awim/memory_gateway/runtime.py
M	src/nerve_awim/memory_gateway/service.py
M	src/nerve_awim/memory_gateway/session.py
A	tests/test_galahad_gpu_smoke.py
A	tests/test_memory_inference.py
A	tests/test_memory_operations.py
A	tests/test_memory_policy.py
```

This report, the historical-report pointer, the updated matrix note and hardening evidence are added in the final documentation commit. The cumulative implementation inventory is available with `git diff --name-status ca1e2d92608654ab5d88c2a5866037656caf4a29 HEAD`.
