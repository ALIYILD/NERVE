# Overnight run, 15–16 October 2026

Base: `fc1fd4f6e3a1de7f9b5f2013365bc9408288e5be`. All inference is Runpod-only; no signing, retention, activation, registry mutation or canonical-gate replacement is authorized tonight.

## Authority and conductor limits

The user explicitly authorized starting pod `lg0svvuenxvbno`, NVIDIA A40, $0.59/hour, with at most **6 cumulative running GPU hours including startup and idle time**, at most 6,000 model calls, wrap-up by 07:00 Europe/London and hard stop 07:30. One same-GPU replacement is permitted only if the original cannot start and is confirmed stopped. Never two running pods. Required model: `qwen2.5-coder:7b`, full digest `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`; mismatch blocks. Every started pod must be stopped and read back `EXITED` before handoff. Only bank-v3 slice1 is conditionally authorized, after the registered dev superiority and no-regression checks. No other holdout is opened.

## Pre-generation resolution and compatibility blocker

The plan's counts conflict: 900 dev + 300 holdout = **1,200**, not 1,300; nine strata cannot each have 43/42 holdout items. Conservative resolution, agreed by the orchestrator before generation: 100 dev per stratum, holdout 34 for the first three and 33 for the remaining six, divided into three balanced slices of 100. **No bank generation or sealing has occurred.**

A CPU-only compatibility probe of the exact retained pipeline found that the requested new sentence family and qualified measurements cannot execute the mandated bootstrap baseline. The frozen `scientific_candidate_v3.prepare(..., arm='baseline')` raises `supported_baseline_input_required`; the candidate routes to deterministic abstention with `unsupported_evidence`. The frozen compact parser only supports the original `Sample X has measurement value unit.` grammar and at most eight current facts; the proposed 6–12 records can exceed that limit. Numeric conflict comparison and numeric scoring already use `Decimal`, so numeric equality normalization is not an unimplemented v4 hypothesis.

Evidence: `evidence/overnight-contract-compatibility.json`. These are public synthetic protocol fixtures, not bank-v3 instances or measured efficacy. Model calls: **0**. Changing the input adapter/registered baseline or silently translating all new templates would change the experiment. Under L0's blocker rule, the GPU study is blocked; preserve the exact retained baseline and report the incompatibility. No pod start is needed to discover this.

## Loop journal

| Loop | UTC start/end | Status/verdict | Calls | Incremental GPU cost | Blocker |
|---|---|---|---:|---:|---|
| L0 | 2026-10-15 22:44 / ongoing | conservative protocol audit | 0 | $0 | family-B input is outside frozen baseline domain |
| L1.1 | 2026-10-15 22:46 | 17 protected files snapshotted, including trust and complete contract files | 0 | $0 | none |

Runpod `get_pod` read on 2026-10-15 at approximately 22:48 UTC: `lg0svvuenxvbno` **EXITED**, rate $0.59/hour, NVIDIA A40. No pod has been started by this overnight run. Retained storage continues billing separately.

Authorized plan preserved as `overnight-orchestration-plan-20261016.md`, SHA-256 `81b1ff05a261a43c1634d1f439514838312d6061cb6f8bdee72d74e2336f8149`.
