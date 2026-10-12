# Original master-plan acceptance matrix

**Continuation update:** [18-hardening-report.md](18-hardening-report.md) supersedes the anchor below for durable scope revocation/deletion, atomic audit/utility cleanup, optional local inference, operational metrics/alerts and manifest-based readiness. These are now implemented and locally tested in commit `5802bb8372f9355ad4f5cb99fa305600c2bbaa4a` (1,038 full-suite passes). Real inference was tested against an HTTP fixture only. General clinical conflict resolution, broader optimiser candidates, real Clinical OS wiring, encrypted operational infrastructure, real KV connector and GPU evidence remain incomplete as listed below. Historical anchor entries are retained to distinguish earlier gaps from this continuation.

Audit anchor: `6ce176e7812e66f18f3fe71cd628b78e7073a1f3`, branch `feature/galahad-persistent-memory`, 12 October 2026. This is an evidence map, not a declaration that the entire specification is complete. Concurrent continuation work must replace a gap only after its tests and execution artifacts exist. The previous full-suite checkpoint was **992 passing tests**, recorded in [validation-wiring.json](evidence/validation-wiring.json); it does not pre-validate later edits.

**VERIFIED** means the stated local synthetic behavior was exercised. **PARTIAL** means meaningful code exists but the full requirement remains unmet. **MOCKED** means a fixture, not hardware evidence. **MISSING** means local engineering remains. **BLOCKED** means external hardware, rights, operator or governance evidence is needed. No component is deployed, and no production/clinical approval is implied.

## Phases and ownership boundaries

| Original phase | Status at audit anchor | Actual evidence / unresolved work |
|---|---|---|
| 0 Discovery and baseline | VERIFIED for local repository | [Audit](00-repository-audit.md), branch/base recorded; actual memory, OIDC, agents and recursion reused; baseline875 then992 tests. Inventory is broader than implementation. |
| 1 Parallel specialists | VERIFIED for coordinated work | Non-overlapping provider/API/gateway/test ownership and independent security review; no ten-agent simultaneous fleet claimed. Coordinator owns integration. |
| 2 Memory Gateway | PARTIAL | `gateway.py`, `contracts.py`, `lifecycle.py`; verified text lifecycle and scope. Real KV admission/deposit/restore absent; global clinical consent absent. See operation matrix. |
| 3 Galahad/runtime | BLOCKED / PARTIAL metadata | `galahad_adapter.py`, preflight and cited compatibility review; no installed compatible runtime/licence/GPU or provider-side identity proof. New passive HTTP capture tool is described below; it is not a connector implementation. |
| 4 Retrieval selection | PARTIAL | Existing SecureMemoryRetriever, bounded advisory IDs, atomic fresh scoped snapshot, SHA-256 content checks and evidence links. Optional ranker failure falls back. No semantic conflict resolution or enforced external-ranker wall deadline. |
| 5 Multi-agent integration | PARTIAL | Existing DemoAgentBridge consumes approved allowlisted hints; existing parallel workers and official MCP2.3 stdio exercised. Other specialists, WorldCore/model inference and real Clinical OS not connected at anchor. |
| 6 Recursive optimisation | PARTIAL | Existing bounded v1.9 loop, deterministic data-only retrieval candidates and one-use independent holdout interface. Public demonstration fixtures are not sealed independent evidence. Broader TTL/admission/KV threshold candidates and representative benefit absent. |
| 7 Benchmarks | PARTIAL | Actual CPU text-retrieval study plus matched gateway variants; no-memory dispatch explicitly unequal capability. GPU/prefix/Galahad and hardware cost controls absent. |
| 8 Security/privacy | PARTIAL | Pinned signed identity, scoped grant intersection, revocation, quotas, minimisation and CPU abuse fixtures. Encryption/key management, real TLS deployment, consent, backup erasure and clinical governance unresolved. |
| 9 API/Clinical OS | PARTIAL | Versioned OpenAPI, client, actual signed HTTP, synthetic context and provenance; agent/MCP host wiring. Inference returns501 at anchor; no real Clinical OS client or clinical authority. |
| 10 Reliability/ops | PARTIAL | Actual SQLite process crash/rollback, cross-process quota admission, concurrent local HTTP and failed invalidation fixtures. Runtime GPU faults, encrypted backup restore, dashboards/alerts and end-to-end operational ownership absent at anchor. |
| 11 CI/release gates | PARTIAL | CPU workflow exists; local gate commands passed at checkpoint. Remote CI, shadow, canary and governance not executed. See gate matrix. |
| 12 Acceptance | PARTIAL | Individual criteria tracked below; unresolved GPU gates are not waived. |
| 13 Bounded coordinator | VERIFIED locally, overall incomplete | Dependency-ordered iterations, independent review and real test artifacts across three checkpoint reports; no arbitrary code executor or automatic production promotion. The eight-cycle budget is not proof that all requirements passed. |
| 14 Deliverables | PARTIAL | All numbered00–13 documents and later continuation reports exist; commands for available local gates exist. GPU evidence, live deployment and external approval artifacts do not. PR URL absent because no PR was created. |

## Gateway operations and retrieval behavior

| Requirement | Status | Evidence / gap |
|---|---|---|
| 1 Propose memory | VERIFIED | Gateway/session/API create pending ledger rows; input bounds and durable quotas apply. |
| 2 Verify/reject memory | VERIFIED | Trusted host delegates to v1.8 review; agents and MCP cannot approve. |
| 3 Retrieve approved scoped memory | VERIFIED | Tenant/agent/context, approval, expiry and integrity checked against a fresh SQL snapshot. |
| 4 Retrieve eligible KV | BLOCKED | Canonical identity exists; no provider currently admits runtime KV. |
| 5 Save KV | BLOCKED | Explicit unsupported operation; no invented deposit API. |
| 6 Invalidate incompatible/revoked memory | PARTIAL | Text revoked/superseded records excluded; provider invalidation failure explicit. No physical Galahad purge proof. |
| 7 Revoke patient/session/agent permission | PARTIAL | Host capability revocation exercised; durable cross-process clinical consent/revocation not at anchor. Scope-specific data revocation is distinct from identity revocation. |
| 8 Delete scoped memory/cache objects | PARTIAL | Exact-context record deletion and quota release exercised; bulk scoped deletion and provider/snapshot erasure incomplete. |
| 9 Lifecycle metadata/status | PARTIAL | Existing ledger status and gateway health; no full remote privileged metadata administration. |
| 10 Sanitised metrics | VERIFIED locally | Scope-bound counters and role checks; no raw clinical text labels. Operational dashboards missing at anchor. |
| 11 Fallback | VERIFIED for fixtures | Ranker outage → same authorised ledger; unavailable KV → prefill. Authentication failure propagates, never becomes unrestricted fallback. |
| 12 Health/readiness | VERIFIED locally | Corrupt/missing ledger and unavailable provider reported separately; healthy text does not mean KV-ready. |
| Full cache identity | PARTIAL | Model/revision/tokenizer/runtime/quantisation/attention/prompt/tokens/instructions/adapter/source/scope fields change hash; unknown forces ineligibility. No proof Galahad's lookup enforces these fields. |
| Application/user/clinic/patient/session separation | VERIFIED for synthetic grant fixtures | Host hashes all dimensions into ledger context; exact clinical request matching; no real clinical identity/consent authority. |
| No relevant, unverified, expired, revoked or deleted records | VERIFIED | Exclusion and abstaining empty context fixtures. |
| Conflicting or superseded facts | PARTIAL | Supersession enforced; demo strategy-hint conflict falls back. General clinical contradiction resolution is not implemented. |
| Unsupported model/stale prompt | PARTIAL | Identity metadata test and universal runtime miss; actual wrong-model GPU-cache rejection untested. |
| Corrupt cache | MOCKED / BLOCKED | Broken provider and corrupt text fixtures; no Galahad encrypted-block corruption execution. |
| Retrieval timeout | PARTIAL | API socket inactivity limits; external ranker execution deadline/circuit breaker missing at anchor. |

## Explicit Phase12 and first-release criteria

| Criterion | Status | Evidence / remaining acceptance |
|---|---|---|
| All existing tests continue to pass; zero regression | VERIFIED at anchor | Full992-test checkpoint; rerun after every later edit. |
| Every introduced API has contract/error tests | PARTIAL | Signed identity, schema, error paths and real HTTP exercised; exhaustive OpenAPI response-schema validation and future inference route still needed. |
| Galahad optional | VERIFIED | Legacy source tests, Null mode and unavailable-Galahad demo pass. |
| CPU-only mode | VERIFIED | Entire gateway, API, agent and MCP synthetic path operates without Galahad. |
| Unsupported runtimes fail gracefully | VERIFIED for unavailable-provider fixtures | Ordinary approved text prefill; runtime connector failure path untested. |
| Cache version mismatch forces recompute | PARTIAL | Strict metadata identity and fail-closed admission; no live mismatched-runtime restore exercise. |
| Durable restart restoration on compatible runtime | BLOCKED | SQLite restart is tested; it is not KV restoration. Linux/GPU/licence and runtime adapter needed. |
| Cross-tenant isolation; zero observed leakage | VERIFIED on defined CPU fixtures | Tenant/agent/clinical scopes and identical-context attempts; GPU prefix/cache/storage isolation unverified. |
| Revocation/deletion verified | PARTIAL | Defined local ledger fixtures pass; distributed identity revocation/provider invalidation/backups remain separate gates. |
| Agent cannot override security gates | VERIFIED for implemented paths | Signed role plus grant, host capability checks, strict hints, no remote approval or arbitrary execution. |
| All deterministic KV restore checks pass | BLOCKED | No tensor or complete logit restoration test run. |
| Corruption rejection100% on defined KV fixtures | BLOCKED | Defined CPU content corruption tests pass; not defined GPU corruption fixtures. |
| Galahad-unavailable fallback100% on defined fixtures | VERIFIED | Provider absence/failure returns approved text; no stored-KV validity inferred. |
| Every performance claim includes environment/sample/baseline | VERIFIED for committed CPU study | Thirty samples, hardware/interpreter and unequal controls labelled in benchmark artifacts. |
| Cold/warm/restore/recompute reported separately | PARTIAL | CPU first/subsequent text timings recorded; GPU states unmeasured. New HTTP probe labels phases as operator-declared. |
| KV correctness separate from answer accuracy | VERIFIED as contract, BLOCKED measurement | No shared metric or conflated pass claim. |
| No improvement claim without representative evidence | VERIFIED reporting constraint | CPU overhead reported; no Galahad speedup claimed. Representative workload study absent. |
| Independent holdout not repeatedly tuned | PARTIAL | Persistent one-use holdout evaluator tests; no independent external corpus/results supplied. Public fixture exercise not sealed. |
| Zero improvement accepted | VERIFIED | Bounded loop may retain baseline; no performance promotion threshold bypass. |
| Synthetic Clinical OS end-to-end executable | PARTIAL | Signed synthetic service→gateway→existing demo agent workflows; real Clinical OS app adapter/model reasoning absent. |
| Clinician/patient authorisation at boundary | PARTIAL | Signed principal/grant/synthetic patient fixture enforcement; actual clinician/consent integration absent. |
| Provenance preserved | VERIFIED | Source IDs and SHA-256 linked to approved records and selected hint; corruption filtered. |
| Rejected/revoked evidence excluded | VERIFIED in defined CPU tests | Fresh bounded SQL snapshot and host revocation; in-flight reads linearise at snapshot, not retroactive cancellation. |
| Clinical output requires authorised review | PARTIAL | API states review_required and synthetic_only; no approved clinical review UI/workflow, and no clinical output deployment. |
| No live deployment claim without approval | VERIFIED reporting constraint | No deployment/pilot/canary/clinical approval claimed. |

## Security and operations requirements

| Requirement | Status at anchor | What closes the gap |
|---|---|---|
| Trusted auth boundary and clinical context authorisation | PARTIAL | Existing pinned OIDC exercised; connect approved IdP/consent in separately governed workflow. |
| Encryption at rest and key ownership | BLOCKED | Plaintext research SQLite; approved encrypted backend/key management and wrong-key/rotation/recovery evidence required. Vendor statements are not local evidence. |
| TLS network interfaces | PARTIAL | HTTPS reference client, loopback-only research host; production TLS terminator/config/cert handling not deployed/tested. |
| Secrets outside Git/prompts | VERIFIED workflow practice | Ephemeral fixture keys; operator environment/config; no secret values in evidence. No universal secret-scanner guarantee. |
| Audit logging without payloads | PARTIAL | Payload-free counters and quiet HTTP errors; durable correlated event audit sink missing at anchor. |
| Retention/revocation/deletion | PARTIAL | Expiry and local deletion; scheduled retention, durable consent, backup lifecycle and provider erasure unresolved. |
| Rate limits/storage quotas | PARTIAL | API rate limits process-local; SQL quota triggers cross-process per scope; aggregate disk/storage-byte cap and distributed API limits missing. |
| Fail-closed access | VERIFIED locally | Unissued/forged/revoked capabilities and invalid signatures rejected; no external clinical validation. |
| Dependency/supply-chain scanning | PARTIAL | Local scans recorded; no GPU wheel review or reproducible native binary attestation. |
| Data minimisation/purpose | VERIFIED for demo outcomes | Fixed task/strategy/completion fields; no raw email/result/task ID; proposal text still must be synthetic. |
| Secure backup/recovery | BLOCKED / MISSING | SQLite transaction rollback tested; encrypted backup restore/replica/key destruction not verified. |
| Cache poisoning/persistent injection/stale medical evidence | PARTIAL | Pending review, strict data-only strategy schema, supersession and source checks. No claim of arbitrary LLM prompt-injection immunity or medical correctness. |
| Wrong-key/full-disk/store-down/connector-crash/model-upgrade | PARTIAL / BLOCKED | CPU provider exception/store corruption tests; exact runtime faults require controlled Linux environment. |
| Concurrent I/O/quota eviction/retry storms | PARTIAL | Real process quota races and bounded local HTTP exercised; GPU eviction/admission/retry/circuit-breaker policies untested. |
| Metrics/dashboard/alerts/traces | PARTIAL | Local counters only at anchor; continuation operational artifacts require independent execution. |
| Clinical assessments | BLOCKED | Separate responsible owners must assess UK GDPR/NHS DSPT/DTAC/DCB0129/DCB0160 and applicable regulatory requirements. No legal determination or clinical approval is supplied by software tests. |

## Benchmarks and release gates

| Required benchmark/control | Status |
|---|---|
| A no memory | Measured empty dispatch only; unequal capability explicitly labelled. |
| B existing verified text retrieval | Measured CPU baseline. |
| C ordinary runtime prefix caching | BLOCKED: no operator runtime measurement. |
| D retrieval + Galahad restore | BLOCKED: real connector and durable restoration absent. |
| E bounded adaptive retrieval | Local synthetic candidate comparison; no GPU improvement claim. |
| F equivalent-budget/capability controls | PARTIAL CPU; model/runtime controls missing. |
| Exact tensors/full logits/random-depth/incorrect-block tests | BLOCKED real runtime. HTTP selected-token probabilities are not full logits. |
| TTFT/prefill/restore/E2E tokens/hits/misses | CPU text overhead measured; passive HTTP probe can collect single-request wall time and reported usage. TTFT/prefill/restore attribution absent. |
| GPU VRAM/energy/disk throughput/storage per token/ingestion/break-even/concurrency/cost | UNMEASURED; report null, not estimated savings. |
| Anti-cheat corpus/blind ingestion/decoys/negative controls/store audit/held-out keys | PARTIAL small public synthetic cases; paper-scale protocol not reproduced. |
| Level0 CPU | VERIFIED at anchor; rerun new tests. |
| Level1/2 real GPU / medium study | BLOCKED approved runtime, model and licence. |
| Level3 50M paper reproduction | OPTIONAL and BLOCKED; no infrastructure/storage allocated. |

| Release gate | Status |
|---|---|
| 1 Static/unit/dependency/schema | PARTIAL local passes; comprehensive types/schema/native supply-chain and remote CI absent. |
| 2 Memory correctness | VERIFIED on defined CPU fixtures. |
| 3 KV correctness | BLOCKED; metadata/fallback tests are insufficient. |
| 4 Security | PARTIAL CPU defined-scope tests; encryption and runtime isolation absent. |
| 5 Benchmarks | PARTIAL CPU; no matched GPU controls. |
| 6 Authenticated synthetic integration | VERIFIED for local HTTP+demo+MCP; model inference/real Clinical OS incomplete at anchor. |
| 7 Shadow deployment | NOT DEPLOYED. |
| 8 Controlled canary | NOT AUTHORISED / NOT DEPLOYED. |
| 9 Clinical governance | BLOCKED separate formal assessment/approval. |

## Passive runtime evidence harness added in this continuation

`scripts/galahad_gpu_smoke.py` is a **real HTTP capture client**, despite its historical smoke filename. It sends a bounded synthetic request to an existing operator-approved vLLM-compatible endpoint; it does not launch processes, acquire hardware, install packages, accept licences or stop/restart anything. `capture` exit0 means a validated observation was written; `compare` exit0 means comparable artifacts were analysed. Neither means the KV release gate passed.

The [Galahad connector guide](https://github.com/corbenicai/galahad/wiki/vLLM-Connector) documents runtime-managed connector configuration, explicit recompute-on-load-failure policy and connector counters in server logs. The guide's compatibility guidance still requires independent checking for the installed package. The [current package page](https://pypi.org/project/galahad-kv/) lists1.32.0, yanked research1.31.4, Linux x86-64 and a non-commercial free option; it requires separate serving processes/stores/keys for untrusted customers and pins vLLM0.30. No licence rights were independently verified here.

The [vLLM API guide](https://docs.vllm.ai/en/latest/serving/online_serving/openai_compatible_server/) documents completions and optional selected-token logprobs. The [metrics guide](https://docs.vllm.ai/en/latest/usage/metrics/) documents `/metrics` and distinguishes ordinary from external prefix counters. These metrics can change by version and may aggregate other requests. They do not establish Galahad attribution, tensor equivalence or a complete GPU-worker restart.

On a reviewed isolated runtime, an operator may collect observations using a fresh random32-hex run ID (reuse it only within the paired experiment):

```sh
python3 scripts/galahad_gpu_smoke.py capture \
  --endpoint http://127.0.0.1:8000 --allow-loopback-http \
  --model OPERATOR_SERVED_MODEL --model-revision IMMUTABLE_REVISION \
  --run-id 0123456789abcdef0123456789abcdef --phase cold --output cold.json
# Repeat the identical request with --phase warm --output warm.json.
# Operator performs and separately records the approved complete engine restart.
# Repeat with --phase after-restart --output restarted.json.
python3 scripts/galahad_gpu_smoke.py compare \
  --before cold.json --after restarted.json --output comparison.json
```

Replace the illustrative run ID; do not use a previously ingested run as a cold control. Supply credentials only through `--bearer-env VARIABLE_NAME`. Redirects are refused. Artifacts contain output and selected-logprob hashes, never bearer credentials or answer/token strings. Existing evidence files are not overwritten. Labels cold/warm/after-restart and model revision are operator declarations, not verified facts. A changed reported HTTP process-start metric is not proof every GPU worker restarted. All outputs retain `kv_release_gate: blocked` until separate runtime/security/tensor evidence is implemented and reviewed. No CLI flag unlocks the NERVE provider.

`tests/test_galahad_gpu_smoke.py` uses a synthetic loopback HTTP server for transport and comparison tests. It is explicitly **MOCKED runtime telemetry**, not a GPU benchmark. No real endpoint has been probed in this work.

## Highest-priority unfinished work

1. Local software: complete provider-independent inference/service integration, durable host policy/consent, bounded audit/operations, precise release reporting and broader reproducible controls; continuation work is underway separately. Retest rather than assuming completion.
2. External runtime: approved isolated Linux NVIDIA host, operator model/revision, compatible Galahad/vLLM versions and licence rights. Then run real deposit/restart/restore, model mismatch, cross-domain prefix, encrypted corruption/deletion and tensor/logit checks. Passive HTTP captures support these tests but cannot replace them.
3. Governance/deployment: named operational owner, TLS/secrets/backup/retention deployment evidence, then separately authorised shadow/canary. Clinical safety approval remains a distinct gate before any real patient data or clinical decisions.

All requested00–13 documents exist, but existence is not acceptance. The local reports provide branch/commit IDs, changed files, test counts, benchmark methodology and reproduction commands. GPU/clinical blockers must remain visible in the final report; no PR/deployment URL can be supplied for an action that has not occurred.
