# Infrastructure verdict and transport policy v2

The current gate verdict for slice 1 is **incomplete_infrastructure**, superseding
its historical `retain_incumbent` label. This is neither evidence against v3 nor
permission to promote it. The original receipt, code and private evidence remain
unchanged and independently replayable. [Reclassification receipt](evidence/scientific-v3-slice1-reclassification.json).
New dry-run and slice-2 execution use `scientific_v3_holdout_v2`, whose incomplete
branch emits the distinct verdict. The historical slice-1 API remains a replay
interface; current workflow entry points are versioned explicitly.

## Transport registration

The immutable [v3 development receipt](evidence/scientific-candidate-v3-study.json)
records `rows[].elapsed_seconds` for each model call. The per-arm maxima and
registered per-attempt timeouts are:

| Arm | Recorded calls | Maximum seconds | Timeout = 3 × maximum seconds |
|---|---:|---:|---:|
| Baseline | 100 | 17.86466720100725 | 53.59400160302175 |
| V3 | 60 | 27.741515359957702 | 83.22454607987311 |

These recorded intervals include host authorization overhead. There is no
rounding, fitted latency target, prompt change or new output limit. Controls and
deterministic abstentions make no model calls. Model policy is pinned to the
source hashes from development commit `cb65c81`.

A transport timeout permits at most **two resends**, hence three attempts per
logical call. Each resend uses the same URL, method, explicit HTTP headers and
exact request body bytes. Seed, messages, response schema, model, temperature
and output cap stay unchanged. The first completed response is returned to the
original v3 validation/scoring code. Parser errors, HTTP failures, authorization
failures and incorrect answers never trigger resends. Every attempt is durably
claimed before network dispatch and records its request hash, timeout, outcome
and elapsed time. Successful raw wire bytes remain in private gate evidence,
even if later parsing fails. Verification reconstructs requests with the original
v3 builder and checks their hashes without networking.

This is a transport adapter around the unchanged v3 request builder, not a change
to v3's source. Calls are serialized and the adapter is restored after each call.
A timed-out server operation can continue; retries do not guarantee exactly-once
server execution. The gate reports physical attempts separately from logical
model calls. No completion is chosen based on correctness. The inherited
7,200-second wall budget and 160-logical-call budget remain; the physical attempt
ceiling is 480.

## Dry-run requirement and machine conditions

The dry run uses the **same new holdout harness** with the 100 original development
items in place of sealed input. It uses the same task order, four arms, policy,
scoring and transport settings as slice 2. Slice-2 registration requires all 400
rows and **160 logical calls / exactly 160 physical attempts**, **zero timeouts**,
and no observed competing workload. A successful retry is not a zero-timeout
qualification. The dry receipt, source hashes, transport policy and runtime
version are bound into the slice-2 registration. No slice-2 item is read during
registration or the dry run.

A literal process-free machine is impossible while macOS, Ollama and the harness
run. The proposed operational interpretation is no competing compute workload:
process names/CPU use are sampled at preflight and every row boundary, without
capturing command arguments. A non-essential process at >=5% CPU prevents
consumption at preflight or stops an active run as infrastructure-incomplete.
System/session/model services necessarily remain. Sampling is not scheduler
isolation, GPU-idleness proof, or a guarantee that no brief workload occurred
between observations. Unrelated applications are not terminated automatically.

## Slice-2 gate

Only after a qualifying dry run may slice 2 be registered. Complete evaluations
use the original acceptance rule: candidate strict total beats all three controls,
and no stratum falls below always-abstain. The verdict is `promote_proposal` or
`retain_incumbent`; incomplete evaluations return `incomplete_infrastructure`.
95% Wilson intervals and component counts are reported per stratum, with the
same descriptive interpretation. No promotion occurs automatically.

All item-level results remain private. The reserve and original combined holdout
stay sealed. The untested recency/agreement strata and the requirement to seal a
new bank before designing a subsequent candidate remain unchanged. This work
must stop at the verdict or an unresolved admission blocker; it must not consume
slice 2 to compensate for a failed dry run.

## Commands

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_scientific_retry_holdout.py
PYTHONPATH=src .venv/bin/python scripts/run_scientific_v3_holdout_v2.py observe
PYTHONPATH=src .venv/bin/python scripts/run_scientific_v3_holdout_v2.py verify \
  --directory /Users/aliyildirim/nerve-research-runs/scientific-v3-transport-dry-v2
```

Verification is read-only and performs no inference. Run commands consume their
registered study once; there is no restart/reroll after consumption.

## Recorded status: blocked before consumption

The [transport registration](evidence/scientific-v3-transport-policy-v2.json) is
frozen with SHA-256
`4cb865908f0ea0edb5a63b93af16155898cdab1479ce013ce18649b2696de52e`.
The [100-item development dry-run registration](evidence/scientific-v3-transport-dry-v2-preregistration.json)
is frozen with SHA-256
`b38c61d87d6733357ea7d5b3b0a9720cee035d221b04e5c741db0a0797620701`.
Its source pins match; no consumed marker or attempt database exists.

Eight focused tests, including a full 400-row/160-call mocked run of this harness,
passed in 195.097 seconds. An earlier fixture run detected source edits during
execution and was rerun after those edits. The final process-check refinement
explicitly treats virtual machines/background compute as competing work, even
when their executables live under a system directory; three focused checks
passed afterward in 0.052 seconds. These are mock/CPU test results, **not** the
requested real 160-call dry run. The historical fast suite was not rerun.

[Preflight evidence](evidence/scientific-v3-transport-preflight.json) records two
failed idle checks. The second observed VirtualMachine PID 1497 at 38.3% CPU,
Git at 73.2%, and Python at 96.0%. No unrelated workload was terminated.
**Zero real dry-run model calls have been made.** Slice 2 has not been registered
or opened; slice 1, slice 2 and reserve retain mode `000` and are unreadable.
No zero-timeout claim or new holdout verdict is available. The current slice-1
verdict remains **incomplete_infrastructure**.

The prerequisite to continuation is an idle machine under the agreed workload
interpretation. Once that prerequisite is met, the still-unconsumed registered
dry run can be started with:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_scientific_v3_holdout_v2.py run \
  --directory /Users/aliyildirim/nerve-research-runs/scientific-v3-transport-dry-v2
```

A blocked preflight performs no input consumption or inference. Once consumed,
the run cannot be rerolled. A completed run containing any timeout, even one
recovered by an identical resend, cannot authorize slice 2. Only a qualifying
verified dry receipt enables its separate registration. No promotion is executed
by either path. These new changes remain uncommitted; v3 stays at `cb65c81`.


## Staged external-methods follow-on

See [implementation and limits](79-external-methods-adoption.md), drawing on [Lewis](https://openreview.net/forum?id=4ob0d33A2l). This follow-on does not change this document's historical registration or evidence claims.
