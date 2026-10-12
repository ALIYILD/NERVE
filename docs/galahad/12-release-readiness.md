# Release readiness

Research checkpoint only. CPU evidence is local; newly added CI workflow has not run remotely. No merge, shadow deployment, canary or clinical deployment.

| Gate | Status | Evidence / blocker |
|---|---|---|
| Existing regression | PASS baseline | 875 baseline; 926 final tests, zero failures |
| CPU correctness/security | Locally tested | Gateway/provider/API/evaluation suites |
| Static syntax | Locally tested | compileall and diff checks |
| Dependency scan/types | Partial | pip-audit: 4 existing locked packages, no known vulnerabilities; no new type/lint toolchain |
| KV correctness | BLOCKED | No supported GPU/runtime/licence, identity/isolation/deletion admission unverified |
| Benchmarks | PARTIAL | CPU latency artifact; no inference/prefix-cache/GPU/cost measurements |
| API integration | Locally tested synthetic | Real signed JWT and local HTTP client fixture; no production IdP or Clinical OS deployment |
| Shadow/canary | BLOCKED | Operational ownership/ingress/distributed controls not validated; human-authorised only |
| Clinical governance | BLOCKED | Separate assessments and approval required before live patient use |

Defined corruption fixtures cover ledger format and content hash, not KV tensors. Defined fallback fixtures cover absent/throwing metadata providers and optional ranker failure, not real connector faults. Cross-tenant tests show zero leaks in finite fixtures, not proof of universal isolation. Encrypted storage/deletion is not implemented by the gateway.

Development cycles: (1) audit/baseline and additive implementation; (2) independent review reproduced three security defects, targeted repairs and regression tests; (3) integrated verification and evidence report. Maximum eight not needed: further hardware integration blocked on Linux/GPU/licence and verified upstream contract. Software deliverable remains partial relative to full master specification; operational and scientific extensions are itemised rather than presented as completed.
