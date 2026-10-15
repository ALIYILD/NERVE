# Provider compatibility and activation gates

Status: **BLOCKED for real KV execution; CPU fallback implemented separately.**
Discovery date: 12 October 2026. No package, licence, model, key or GPU was installed or activated for this work.

## Upstream evidence

[PyPI](https://pypi.org/project/galahad-kv/) lists proprietary beta release 1.32.0, uploaded 12 October 2026; the paper's 1.31.4 release is now yanked. Its published description specifies Linux x86-64, Python 3.10–3.14 and a non-commercial one-GPU free licence. It warns: “One serving process = one trust domain.” Separate processes, stores and keys are required for mutually untrusted customers. Package metadata pins vLLM 0.30 and SGLang 0.5.20. A package installation is neither a licence check nor security evidence. Commercial rights remain unverified.

The [paper](https://arxiv.org/html/2610.10845v1) describes Galahad 1.31.4 with vLLM 0.31.0 on an H100 and local NVMe. Those reproduction pins conflict with current package guidance; neither combination is approved here. Its KV restore and language-model answer correctness are separate measurements. Its results are external research, not NERVE measurements.

The [vLLM connector guide](https://github.com/corbenicai/galahad/wiki/vLLM-Connector) describes plugin discovery and runtime-managed deposit/restore. Its documented connector settings are:

```json
{"kv_connector":"GalahadConnector","kv_role":"kv_both","kv_load_failure_policy":"recompute"}
```

The guide uses `GALAHAD_CACHE_DIR`, `GALAHAD_KEY_FILE` and `GALAHAD_LICENCE_FILE`. It reports testing on vLLM 0.30. It states failed cache loads can recompute when configured; the default failure policy instead errors. This configuration is reference material, not a NERVE launch command or evidence of safe integration.

The [tenant guide](https://github.com/corbenicai/galahad/wiki/Tenant-Isolation) describes a multi-tenant mode and tenant erasure in the C interface. These claims do not resolve the more restrictive package warning. They also do not establish deletion across snapshots or backups, nor patient/application/agent isolation inside a tenant. NERVE must preserve all of those boundaries and cannot substitute a tenant identifier for authentication.

The [collision guide](https://github.com/corbenicai/galahad/wiki/Collision-Safety) distinguishes confirmed from single-hash lookups. It recommends forced-collision verification. NERVE's SHA-256 identity does not prove the runtime actually binds all identity fields to its cache lookup. Source, instruction, model revision and authorised scope changes must force recomputation in the runtime as well.

## Local observation and implementation boundary

Initial interpreter: Darwin x86-64, Python 3.10.0; `galahad-kv`, `vllm`, `sglang` and `nvidia-smi` absent. This is an unsupported host for the published binary. The preflight reports observations without importing optional packages, loading native code, reading licence/key values, making network calls or starting a process.

`NullKVProvider` has no storage and always chooses ordinary prefill. `GalahadKVProvider` is a fail-closed admission adapter: even when packages are present, identity validation returns false, invalidation returns false, and health remains blocked. No invented deposit/restore wrapper is supplied. A requested invalidation is not represented as successful physical erasure. The documented connector configuration is available as metadata for a future reviewed runtime integration.

## Evidence required before enabling a provider

1. Supported Linux/GPU/Python/CUDA runtime, reviewed package hashes and verified compatible connector versions.
2. Licence rights for the intended deployment, without recording secret material in artifacts.
3. Per-security-domain process/store/key provisioning; adversarial identical-prefix cross-domain tests.
4. Runtime binding of every NERVE identity field, confirmed collision checks, and immutable model/tokenizer revisions.
5. Measured tensor/token or logit restore correctness, fresh-process restart, corruption and wrong-key refusal.
6. Verified scoped invalidation/deletion, retention, quotas, key ownership and backup handling.
7. Synthetic-only authenticated service tests and independent review.

Run `PYTHONPATH=src python3 scripts/galahad_preflight.py`. Exit 2 means the real provider is blocked; it is not a CPU test failure. Removing these blockers requires a reviewed implementation and evidence, not an environment flag. No speedup, erasure, encryption or GPU correctness is claimed by CPU tests.
