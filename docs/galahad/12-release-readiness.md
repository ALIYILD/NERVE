# Release readiness

Research checkpoint only. CPU evidence is local; newly added CI workflow has not run remotely. No merge, shadow deployment, canary or clinical deployment.

| Gate | Status | Evidence / blocker |
|---|---|---|
| Existing regression | PASS baseline | 875 original baseline; 926 first checkpoint; 951 continuation; 992 wired-integration tests, zero failures |
| CPU correctness/security | Locally tested | Gateway/provider/API/evaluation suites |
| Static syntax | Locally tested | compileall and diff checks |
| Dependency scan/types | Partial | pip-audit: 4 existing locked packages, no known vulnerabilities; no new type/lint toolchain |
| KV correctness | BLOCKED | No supported GPU/runtime/licence, identity/isolation/deletion admission unverified |
| Benchmarks | PARTIAL | CPU latency artifact; no inference/prefix-cache/GPU/cost measurements |
| API integration | Locally tested synthetic | Real signed JWT, local HTTP workflow, actual NERVE agent/parallel calls and official MCP 2.3.0 stdio; no production IdP or Clinical OS deployment |
| Shadow/canary | BLOCKED | Operational ownership/ingress/distributed controls not validated; human-authorised only |
| Clinical governance | BLOCKED | Separate assessments and approval required before live patient use |

Defined corruption fixtures cover ledger format and content hash, not KV tensors. Defined fallback fixtures cover absent/throwing metadata providers and optional ranker failure, not real connector faults. Cross-tenant tests show zero leaks in finite fixtures, not proof of universal isolation. Encrypted storage/deletion is not implemented by the gateway.

Development cycles: (1) audit/baseline and additive implementation; (2) independent review reproduced three security defects, targeted repairs and regression tests; (3) integrated verification and evidence report. (4) continued with atomic SQLite quotas, batch revalidation, concurrent API handling and external one-use holdouts; (5) independent review, crash recovery and 951-test regression. Further hardware integration remains blocked on Linux/GPU/licence and a verified upstream contract. Software deliverable remains partial relative to full master specification; operational and scientific extensions are itemised rather than presented as completed.

Current continuation evidence: `evidence/validation-cycle4.json` and `14-continuation-report.md`. Durable quotas cover ordinary writers sharing the opted-in SQLite database. Rate limits and network grants remain process-local. Holdout reuse is blocked across restart, but independent key custody still requires a trusted operator.

Cycles 6–8 connected existing NERVE agent/MCP entrypoints, validated host configuration and local HTTP serving, repaired independent-review findings, and passed 992 final tests. See `15-runtime-wiring.md`, `16-wiring-report.md` and `evidence/validation-wiring.json`. CI now defines the two HTTP/provider workflows and official MCP smoke; remote CI has not been run.
