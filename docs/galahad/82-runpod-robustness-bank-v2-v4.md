# Development robustness and the next candidate boundary

This continues after slice 2’s `promote_proposal` without signing or installing
v3. All inference and executable validation tests run on the existing Runpod
A40, pod `lg0svvuenxvbno`. Local work is code authoring and evidence handling.
The backend remains Ollama 0.40.5, `qwen2.5-coder:7b`, model digest
`dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`.

## Loop 36.5 design

The complete original development split has 700 items, 100 in each of seven
strata. Its manifest and item content hashes are checked before registration.
The frozen v3 preparation, schema, route, scorer and model settings are reused.
Nothing from slice-2 item results is used to design this study.

Three model seeds (20261015, 20261016, 20261017) use the same shuffled task order,
allowing a descriptive across-seed accuracy variance without also changing
order. A fourth run repeats seed 20261015 with another shuffled order, allowing
a matched paired correctness-flip comparison. Orders are deterministic SHA-256
sorts fixed before inference. Temperature remains zero; requested backend seeds
do not guarantee bitwise reproducibility, and observed seed variance measures
only these three requested settings. This is 2,800 arm rows and 2,000 logical model calls,
with 800 deterministic v3 abstentions. A single-seed order contrast does not
establish a general causal order effect. The first three runs’ stratum failure
counts are item-by-seed observations on reused items, not 300 independent items.

The exact registration hash is
`2a40b2a03777226d0b19fd859314e3e3dff98f3a940ae13ab82669255989bad8`.
Timeouts and journaled retries inherit the frozen Runpod policy: a
39.987594332545996-second per-attempt limit, at most two identical-request
resends, timeout-only, with the first completed response retained. There is a
two-hour wall budget and no automatic rerun after consumption.

Reports retain per-stratum/per-run counts and 95% Wilson marginal intervals.
They also include seed sample variance, paired order gains/losses/flips, measured
physical-attempt median/maximum latency, tokens, wall time, allocated cost,
unchanged model/policy capacity, wrong answers, false abstentions and abstention
precision. A separate domain verifier is not installed; its violation metric is
n/a. UX is n/a. This is exploratory synthetic evidence, not promotion, real-world
safety evidence or unseen-template generalization.

The existing GPU-integration study completed its 160 model calls and exited
before robustness began. The separate outcome proof’s CPU tests completed before
robustness began. Two bank-sealing fixture tests briefly overlapped robustness
for 0.034 seconds of CPU test time, then ran again after integrity hardening for
0.114 seconds. They made no model calls and created no real bank. Thirteen focused protocol tests passed on Runpod before registration.

## Sealed next bank

The CPU-only generator is fixed to 300 new holdout instances: six strata with
43 items and stale-vs-current with 42. A new random private 256-bit seed drives
the existing templates. Generation writes its own registration first, records
the manifest hash, then verifies mode 000 on the holdout and seed before issuing
a sealing receipt. Actual storage is pod-local `/root`, since the `/workspace`
mount does not enforce requested file permissions.

No v4 hypothesis or candidate code may be designed before this receipt exists.
The only failure evidence admitted to v4 design is the robustness aggregate’s
stratum-level counts. No failing task text, raw response or holdout item is used.
The new bank is never evaluated during this continuation. Evidence is copied to
private local backup before the pod can later be stopped.

## Completed robustness measurements

The complete receipt replayed on Runpod without additional model calls.

| Stratum | Seed 20261015 | Seed 20261016 | Seed 20261017 | Matched order repeat | 95% Wilson interval per run |
|---|---:|---:|---:|---:|---:|
| Supported measurement | 100/100 | 100/100 | 100/100 | 100/100 | 96.30–100% |
| Measurement decoy | 100/100 | 100/100 | 100/100 | 100/100 | 96.30–100% |
| Entity decoy | 100/100 | 100/100 | 100/100 | 100/100 | 96.30–100% |
| Unit mismatch | 100/100 | 100/100 | 100/100 | 100/100 | 96.30–100% |
| Conflict | 100/100 | 100/100 | 100/100 | 100/100 | 96.30–100% |
| Multi-source agreement | 100/100 | 100/100 | 100/100 | 100/100 | 96.30–100% |
| Stale versus current | 100/100 | 100/100 | 100/100 | 100/100 | 96.30–100% |

All seven stratum seed sample variances were zero. Every matched order comparison
had 100 paired items, zero correctness gains, zero losses and zero flips. These
are four observations of each of 700 reused development instances, **not 2,800
independent tasks**. No comparative superiority over another policy was tested.

The five axes are:

- **Accuracy:** the per-stratum/run counts and intervals above. The two previously
  untested v3@7B strata have now been measured on development data.
- **Efficiency:** 2,000 logical model calls, exactly 2,000 physical attempts,
  zero timeouts, 2,351.2277474701405 seconds (39 minutes 11 seconds), and 216,264
  measured tokens (154,468 prompt; 61,796 completion). Physical-attempt latency
  median was 1.1068303119391203 seconds and maximum 15.828178808093071 seconds.
  Allocated run cost estimate is $0.38534010305760635 at the live $0.59/hour pod
  rate. This excludes preparation, verification, idle time and other workloads;
  it is not an invoice. Capacity delta is zero for model weights and policy;
  peak GPU memory was not measured.
- **Robustness:** zero measured seed variance and zero matched-order correctness
  flips under this registered design. This does not establish universal order
  invariance or accuracy beyond these synthetic templates.
- **Safety:** 800/800 abstentions were correct (precision 1.0), with zero wrong
  answers and zero false abstentions. This measures synthetic answer integrity;
  a separate domain-verifier violation metric is n/a.
- **UX:** n/a.

## Bank sealed, then hypothesis boundary reached

The new bank was generated and sealed before these outcome counts were exposed
to the candidate-design agent. Sealing time was
`2026-10-15T22:10:34.989480+00:00`. Its manifest SHA-256 is
`786852f3b5b64da13d9ee5238adf7d96c81417095c1ffcf3d7072bf4ccf990e9`.
It contains exactly 300 items across seven strata and made zero model calls.
Generation wall time was 0.042306315153837204 seconds; its allocated cost estimate
is $0.000006933534983545541. The holdout and private seed are mode 000.

**Step 4 boundary: `no_failure_supported_hypothesis`.** Every admitted stratum
failure count was zero across the three seed runs. There is no worst failing
stratum from which to derive the requested failure-directed v4 rule. No failure,
regression risk, candidate, or improvement was invented to force another study.
No v4 candidate was designed or registered, and no v4 development comparison was
run. This is an evidence-supported stop, **not** a tested v4 acceptance/rejection
verdict. v3 remains unsigned; no skill was installed or incumbent superseded.
The new bank was not evaluated.

Remote private evidence remains under `/root/nerve-robustness-20261015/` and the
sealed bank under `/root/nerve-holdout-bank-v2-20261015/`. Private local backups
are under `/Users/aliyildirim/nerve-research-runs/runpod-robustness-bank-v2-20261015/`:
parent mode 0700, archives mode 0600, extracted holdout and seed mode 000. Archive
checksums match the remote copies. Mode 000 is cooperative sealing against normal
access, not an isolation boundary against root or the trusted owner. Runpod was
not stopped or otherwise changed.

Public evidence: [preregistration](evidence/scientific-runpod-robustness-preregistration.json),
[aggregate](evidence/scientific-runpod-robustness-aggregate.json),
[verification and backup bindings](evidence/scientific-runpod-robustness-verification.json),
[bank registration](evidence/scientific-holdout-bank-v2-registration.json),
[bank manifest](evidence/scientific-holdout-bank-v2-manifest.json),
[sealing receipt](evidence/scientific-holdout-bank-v2-sealing-receipt.json), and
[no-candidate boundary](evidence/scientific-runpod-v4-boundary.json).
