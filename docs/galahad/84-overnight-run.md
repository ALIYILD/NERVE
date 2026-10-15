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
| L0 | kickoff / ongoing | conservative protocol audit | 0 | $0 | family-B input is outside frozen baseline domain |
| L1.1 | 2026-10-15 22:47:15 | 17 protected files snapshotted, including trust and complete contract files | 0 | $0 | none |

Runpod `get_pod` read on 2026-10-15 at approximately 22:48 UTC: `lg0svvuenxvbno` **EXITED**, rate $0.59/hour, NVIDIA A40. No pod has been started by this overnight run. Retained storage continues billing separately.

Authorized plan preserved as `overnight-orchestration-plan-20261016.md`, SHA-256 `81b1ff05a261a43c1634d1f439514838312d6061cb6f8bdee72d74e2336f8149`.

### Preflight completion journal

| Loop | UTC start/end | Status/verdict | Calls | Incremental GPU cost | Blocker |
|---|---|---|---:|---:|---|
| L1.2 | 2026-10-15 22:47:15 / 22:53:48 | **blocked: fast tier exceeded protected 180s deadline**; sandbox attempt also failed localhost tests; unrestricted retry showed zero reported assertion failures before timeout, not a full pass | 0 | $0 | fixed fast deadline; no override above 180 permitted |
| L1.3 | 2026-10-15 22:53:48 / 22:54:32 | actual retained skill consumer passed; registry unchanged | 0 | $0 | none |
| L1.4–1.5 | skipped | no pod start or transport smoke after CPU blockers | 0 | $0 | L0 stop rule |
| L3–L6 | skipped | no bank v3 generation/sealing, no candidate, no holdout consumption | 0 | $0 | exact frozen baseline cannot execute family B |

Full fast logs preserved under `/Users/aliyildirim/nerve-research-runs/overnight-20261016/`; hashes and attempts in `evidence/overnight-suite-attempts.json`. The wrapper explicitly refuses fast deadlines above 180 seconds; neither wrapper nor tier manifest was changed. L7 will reuse this final fast outcome and execute slow once, after L2 releases the single-suite lock.

The retained consumer checked all 16 conditions in 40.303 seconds with zero model calls and zero signing calls.

## L2 simulation received, publication pending

The fixed 200-proposal simulation nominally meets zero observed harmful acceptance and lower item consumption, but the sequential gate also accepts **zero of 100 good proposals**. This is not a useful promotion-power result. Sequential: 0/40 harmful,0/60 neutral,0/100 good;16,386 items versus20,000 (18.07% fewer). Naive-reuse current gate: 0/40 harmful,18/60 neutral,100/100 good. Matched fresh-stream diagnostic: 2/40 harmful,30/60 neutral,97/100 good. These are distinct comparisons, not interchangeable causal estimates. No retuning from these results. L2 scoped 18 tests passed; full fast tier remains incomplete.

L7 slow tier launched once at approximately 2026-10-15 22:59UTC with the existing 549-second measured deadline, after L2 released the single-suite lock. It uses CPU fixtures and mocked inference transports. No inference runs on the laptop.

## L7 final wrap-up, 2026-10-15 23:04UTC

- Slow tier: **521 tests passed**, 247.012 seconds (248.462 seconds total gate time), zero failures/errors/skips; one run. Fast tier remains **incomplete at 180 seconds**, not green.
- L2 integrated as `7006ce4` after slow completion to avoid changing source hashes during tests. All 259 registered sources, all 17 original protected files, wallet and evidence hashes, and preexisting discovered test-module hashes still match. L2 has 18 scoped passing tests.
- Fresh `get_pod` at 23:04:07UTC: `lg0svvuenxvbno` **EXITED**. No pod was started or created; running GPU hours 0, model calls 0, incremental compute cost $0. Preserved storage bills separately.
- No bank v3 exists; no v4 was designed, evaluated, signed or retained; no holdout slice was consumed. No canonical gate, trust or registry change.
- The operational workflow closed under its explicit stop rules. The research objective was **not achieved**. Next prerequisites: a separately registered versioned input adapter or compatible harder-bank protocol; a new prospective sequential-power study; and separately authorized repair of the stale fast-tier timing plan.
- **The 8/8 result is prewritten-handler selection, not learning evidence; the fixed best handler also gets 8/8.**

Final decision summary and the complete loop table are in `90-overnight-handoff.md`; the Desktop morning handoff is written after the final push and includes the exact remote head.
