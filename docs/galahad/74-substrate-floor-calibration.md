# Model floor adjudication and substrate calibration

The completed 60-item development study is adjudicated **`model_at_floor`**.
All 100 actual model outputs were `ABSTAIN`; baseline and conflict-check each
matched always-abstain on every item. No policy candidate was distinguishable.
The conflict rule executed mechanically, but its effect on answer quality was
untested in effect because the model already abstained on every conflict.
The original source-pinned study receipt is preserved, including its original
`retain_baseline` decision; a separate adjudication records this interpretation.

## Proposal gate

The versioned substrate gate validates the original completed receipt before
adjudicating it. Its current gated proposal workflow blocks prompt/routing
proposals for the same immutable model digest. Changing a prompt, runtime label
or model alias cannot unblock it. A changed digest must be verified by the host;
it permits renewed research, not promotion or clinical deployment. Historical
proposal primitives remain available for receipt replay; they are not universally
disabled APIs. New proposal work must use the gated workflow.

## Frozen calibration design

This is one diagnostic study, not a promotion study. Ten supported development
items are each presented under three conditions, with declared seed `20261015`:

1. Compact prompt, allowing `ABSTAIN`.
2. The original full JSON prompt template.
3. Compact prompt with its `ABSTAIN` alternative removed, scored for correctness
   only; a forced response is not evidence of improvement.

The repository has no identifiable exactly 490-token prompt. The original template
is reused from `scientific_candidate_execution.prepare` and its existing JSON
transport serialization; actual token counts are reported. The compact format has
a plain text output contract rather than a JSON decoder schema, so the third
condition removes the abstention alternative from that contract.

All conditions receive the same facts and use the same output token ceiling.
The compact/original comparison changes the existing interface bundle (including
serialization), so it does not isolate prompt length alone. Raw text, valid
answers, declared abstentions, malformed outputs and strict correctness are kept
separate. Development reuse is allowed for this diagnostic; no holdout access or
private task-bank seed access is authorized. There are at most 30 calls, no retries,
and an 1,800-second wall budget. The selected roster, schedule, contracts and
source hashes are frozen before inference.

If the original condition abstains on at least nine of ten items, the operational
substrate blocker is recorded as **“1.5B model is the ceiling”**, as requested.
This is a decision to change this study substrate, not a general proof about all
1.5B models. No 7B model is provisioned in this task. Work stops after this report.

## Reproduction and verification

The original development receipt is only read and validated. The current proposal
entrypoint, using the live local model identity, returned `blocked`, zero
proposals and zero inference calls. See [floor adjudication](evidence/scientific-substrate-gate-v1.json)
and [blocked proposal receipt](evidence/scientific-substrate-blocked-proposal-v1.json).
Historical registration commands do not become a universal security boundary;
use this versioned entrypoint for new proposal work:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_scientific_substrate_gate.py \
 --operation propose \
 --study-directory /Users/aliyildirim/nerve-research-runs/scientific-compact-dev-study-v1 \
 --episode-directory /Users/aliyildirim/nerve-research-runs/scientific-episodes-v2
```

The calibration protocol was frozen before any inference in
[the preregistration](evidence/scientific-substrate-calibration-prereg-v1.json).
The following command verifies its terminal receipt without inference. Remove
`--verify` only for the initial execution on registered paths; a completed study
cannot be rerun for another sample. `--prepare` performs registration only.

```bash
PYTHONPATH=src .venv/bin/python scripts/run_scientific_substrate_calibration.py --verify \
 --directory /Users/aliyildirim/nerve-research-runs/scientific-substrate-calibration-v1 \
 --journal /Users/aliyildirim/nerve-research-runs/scientific-substrate-calibration-claims.sqlite \
 --expected-digest d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668 \
 --bank-directory /Users/aliyildirim/nerve-research-runs/task-bank-v1 \
 --bank-manifest-sha256 e11a17a72fb6482dc5978ee5e3c8d4b488f1d71d9c8e060aa382637020718ae6
.venv/bin/python scripts/verify_galahad.py fast --timings /private/tmp/nerve-substrate-fast-check.json
```

The fast tier passed **1,589 tests**, with zero failures/errors/skips, in
107.383 seconds (109.170 seconds for the gate including discovery). This includes
24 new substrate gate/calibration tests. [Timing evidence](evidence/suite-fast-substrate-v1.json).
The unchanged slow tier previously passed 499 tests in one serial run; no new
slow-tier execution is claimed here. Gate tests and calibration transport fixtures
are mocked; the calibration results below describe actual local inference.

## Actual outcome: incomplete calibration

The single registered study stopped after **105.620 seconds** when call 2, the
original-prompt condition, exceeded its 90-second socket timeout. The receipt is
`failed_consumed`: two attempts claimed, one returned response, no completed-study
summary, and no retries. The remaining 28 planned calls were not attempted.

| Condition | Returned / planned | Answer rate among returned | Strict correctness among returned | Execution |
|---|---:|---:|---:|---|
| Compact | 1/10 | 0/1 (0%) | 0/1 (0%) | One `ABSTAIN` |
| Original full prompt | 0/10 | Not measurable | Not measurable | One request timed out; nine unattempted |
| Compact without ABSTAIN | 0/10 | Not measurable | Not measurable | All ten unattempted |

These are partial observations, **not the requested completed ten-item-per-condition
comparison**. The one returned compact output was exactly `ABSTAIN`, with 68 prompt
tokens, four completion tokens and 10.376 seconds of measured call time. No raw
text or usage was received for the timed-out original request. The 90-second
transport ceiling was declared before execution, independently of the 1,800-second
overall budget. No protocol was changed or rerun after this outcome.

The original prompt therefore has **no measured abstention rate**. The ≥9/10
condition was not established, and **“1.5B model is the ceiling” is not recorded**
as a new evidence-based blocker. The existing `model_at_floor` adjudication from
the prior complete 100-call study remains in force. No 7B/GPU transition, policy
proposal, promotion or holdout access followed.

[Actual consumed receipt and raw text](evidence/scientific-substrate-calibration-v1.json).
The `--verify` command validates this failed terminal receipt without dispatch,
prints it and intentionally exits 1 because the study did not complete. Execution
stops here; completing the comparison requires a separately agreed protocol for
handling the original-prompt timeout.

[Read-only verification](evidence/scientific-substrate-calibration-verification-v1.json) disabled network/inference functions, installed the holdout/seed open guard, and confirmed all seven checked artifacts retained their bytes and modification times. Independent review confirmed the same terminal claims and absence of a summary.
