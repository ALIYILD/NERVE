# Tier-6 plan adoption and evaluator foundation

The user supplied `/Users/aliyildirim/Desktop/NERVE_SELF_LEARNING_LOOP_PLAN.md`
on 14 October 2026. A verbatim [plan snapshot](plans/nerve-self-learning-loops-36-45.md)
is retained with SHA256
`01c5346e707c54689f73e64a0b25238a76864f628d5e51c2b770e16d140c8179`.
Its Loops 36–45 now define the additional acceptance requirements; the earlier
NERVE×Galahad scope and clinical boundaries remain in force. This document does
not declare Tier 6 complete.

## Reconciled requirements

- A 300-item total bank with a 70/30 split gives only 90 holdout items, fewer than
  seven strata ×20. The plan also requires a 300-item holdout study. The bank is
  therefore 1,000 items: 700 development and 300 holdout, with 100 development
  items per stratum and 42 or 43 holdout items per stratum.
- Three seeds on 300 holdout items require 900 calls per model arm. At five seconds
  per call, sequential execution would take 75 minutes per arm. Median latency
  alone does not establish a sub-hour total. The GPU study must measure actual
  throughput and total elapsed time; no latency claim is inferred from a model size.
- Always-abstain and deterministic random controls can require zero inference.
  An incumbent control requires exact matched historical predictions or real
  inference. Missing predictions must report no data, never fabricated scores.
- Report output shape, response-contract compliance and factual correctness
  separately. Report end-to-end accuracy and coverage as well; excluding malformed
  answers from a conditional factual score must not inflate the promotion metric.
- Three seeds are repeated observations of the same task, not three times as many
  independent tasks. Future confidence intervals must account for this dependence.
- Repeated adaptive candidates cannot repeatedly consume one holdout as if it
  remained unseen. Bank access guards do not replace Loop 40's one-use study claims
  and preregistered evaluation budgets or fresh partitions.
- A positive learning-curve slope is an empirical result, not something engineering
  can guarantee. Negative findings remain retained evidence.

## Dependency audit

The referenced `NERVE_LOOP_PLAN.md` was not found in this repository or the bounded
Desktop search. Numbered Loops 18–35, F.2 storage and their JARVIS dependencies
therefore remain unverified; repository module version numbers are not proof of
those loop numbers.

| Requirement | Existing reusable code | Remaining integration |
|---|---|---|
| Verified outcome memory | `memory_v18.py`, gateway, `memory_gateway/learning.py` | General episode journal and scientific bank binding |
| Candidate generation | `recursive_evolution_v19.py`, `hermes_learning.py`, `skill_proposals.py` | Failure-cluster scientific hypotheses, negative-candidate policy |
| Skills | `hermes_agents.py`, `skill_model.py`, AgentOS learning modules | Proposed signed scientific evidence bundle and JARVIS view |
| Holdout claims | `memory_gateway/holdout.py`, `governed_learning_v20.py` | New bank/selection gate integration |
| Governed release/rollback | `governed_learning_v20.py`, `promotion_monitor_v24.py` | Clinical report signatures and live workflow governance |
| Scientific coordinator | `scientific_research_coordinator.py` | Powered controls, confidence intervals, generated hypotheses |
| Structured output | `scientific_structured_*` | Actual GPU runtime verification; CPU preflight timed out |
| Signed clinical rewards/JARVIS | No corresponding implementation verified here | External application contracts, synthetic integration, approved traffic |
| Weight learning | No clinical training pipeline verified here | Curated trace volume, governance, training and adapter evaluation |

Existing generation, retention and operator-controlled release components should
be reused. Their existence does not establish the new scientific or clinical
end-to-end requirements.

## Task-bank implementation

`scientific_task_bank.py` builds versioned, exact-decimal synthetic tasks across
supported measurement, measurement decoy, entity decoy, unit mismatch, conflict,
multi-source agreement and stale/current evidence. Evidence includes source ID,
version, current/superseded marker, timestamp and content hash. Each item includes
ground truth, behavior, split, stratum and a content hash. The manifest pins the
schema, interpretation rules, private seed identity, source code and both files.

Stale/current interpretation is explicit: only records marked current participate
in the answer; contradictory current values require abstention. Agreement chooses
the lexicographically smallest supporting source ID under a fixed rule. This
single-citation output rule does not hide the other evidence records in the bank.

Development and holdout contain distinct synthetic instances. They share seven
construction templates and a schema; this is not an unseen-domain or unseen-template
benchmark. A larger item count alone does not prove representative scientific
reasoning or statistical independence.

A trusted host creates a private 0700 directory and 0600 files exclusively. No
existing bank is overwritten. The seed is private and is not included in Git or
model prompts. Only its hash is retained in the manifest. An externally supplied
manifest digest is required to open the bank, so rewriting files and manifest
cannot silently redefine the trusted dataset.

Development access requires a host-issued capability bound to the generator.
Holdout access requires the separately bound selection-gate capability. A generator
call must never open the holdout file. Host integrity checks may hash/validate both
files but do not expose holdout data through the development API. Missing data is
`off/no_data`; corruption is `degraded/integrity_failure` and is not reinitialized.
Disabled reads expose no data.

This is an API and private-file boundary, not a sandbox against a trusted host
with filesystem/source access. Deployment must isolate generator and evaluator
processes/storage. There is no independently sealed external custody claim.

## Actual build and validation

The actual protected bank was created on 14 October 2026 at
`/Users/aliyildirim/nerve-research-runs/task-bank-v1`. Its externally pinned manifest
SHA256 is `e11a17a72fb6482dc5978ee5e3c8d4b488f1d71d9c8e060aa382637020718ae6`.
The private seed remains at `/Users/aliyildirim/nerve-research-runs/task-bank-v1.seed`;
its value and the task/answer files are not committed or printed.

The full regression passed **1,850 tests in 173.568 seconds**, including 41 new tests
this cycle (12 task-bank tests). Independent task-bank review validated the code
and tests, including a separately derived truth check over all 1,000 temporary
fixture items. The actual bank's manifest/source hashes and private file modes
passed integrity verification.

| Stratum | Development | Holdout |
|---|---:|---:|
| Supported measurement | 100 | 43 |
| Measurement decoy | 100 | 43 |
| Entity decoy | 100 | 43 |
| Unit mismatch | 100 | 43 |
| Conflict | 100 | 43 |
| Multi-source agreement | 100 | 43 |
| Stale/current evidence | 100 | 42 |
| Total | 700 | 300 |

The actual generator read returned 700 development items with a guard that raises
if the holdout file is opened. An attempted generator holdout read was denied.
A separate Python process verified host integrity with no inference and left all
three artifact hashes and modification times unchanged. Directory mode is 0700;
all three files are 0600. This is host integrity verification, not a model study or
an opening of the holdout through a candidate generator.

Published evidence contains no actual task answer keys:

- [Pinned manifest](evidence/task-bank-v1-manifest.json).
- [Sanitized build receipt](evidence/task-bank-v1-build.json).
- [Access/restart verification](evidence/task-bank-v1-verification.json).
- [Full regression evidence](evidence/task-bank-v1-tests.json).

The model-generated outputs from the earlier structured preflight remain a failed
attempt, separately documented; task-bank creation does not convert that failure
into runtime support or learning success.

## Reproduction

Inspect the existing bank without displaying any answers:

```sh
PYTHONPATH=src .venv/bin/python - <<'PYVERIFY'
from nerve_awim.memory_gateway.scientific_task_bank import ScientificTaskBank
from nerve_awim.memory_v18 import MemoryAuthority
bank = ScientificTaskBank(
    '/Users/aliyildirim/nerve-research-runs/task-bank-v1', MemoryAuthority(),
    expected_manifest_hash='e11a17a72fb6482dc5978ee5e3c8d4b488f1d71d9c8e060aa382637020718ae6',
    tenant_id='research', generator_agent_id='generator')
print(bank.status())
assert bank.status()['status'] == 'live'
PYVERIFY
```

The creation command used was:

```sh
PYTHONPATH=src .venv/bin/python scripts/build_scientific_task_bank.py \
  --directory /Users/aliyildirim/nerve-research-runs/task-bank-v1 \
  --seed-file /Users/aliyildirim/nerve-research-runs/task-bank-v1.seed
```

Creation is exclusive: rerunning that command now refuses to overwrite the bank.
Retain the private seed and externally pinned manifest. Rebuilding with the same
seed is the same dataset, not fresh holdout evidence. Do not expose seed or answer
files to candidate-generation agents. Run all tests with:

```sh
.venv/bin/python scripts/verify_galahad.py baseline --timeout-seconds 600
```

New implementation files are `memory_gateway/scientific_task_bank.py`,
`scripts/build_scientific_task_bank.py` and `tests/test_scientific_task_bank.py`.
The same cycle added the optional structured-output adapter, raw-output evaluator,
bounded preflight runner/CLI and 29 corresponding tests. Existing source-pinned
scientific studies were preserved. No PR, remote push, deployment or merge occurred.

## Remaining gates

Loop 36.4 is blocked on an approved GPU-backed ≥7B endpoint and compute budget;
the current laptop has Intel UHD 630 and a 4 GB AMD Radeon Pro 5500M, without
`nvidia-smi`. No GPU host was provisioned or charged. The structured CPU preflight
failed on its first unconstrained request; no schema-constrained response was
observed. See [the preflight evidence](63-structured-scientific-preflight.md).

Task-bank construction alone does not complete Loop 36. Statistical gates,
zero-inference controls, matched incumbent evidence and a representative GPU study
remain. Loops 37–45 require the additional journal, signed reward integration,
generation/selection/retention chain, governed shadow/canary, adaptation, and
externally gated weight training. Clinical traffic and unsigned deployments are
not enabled by this work.


## Staged external-methods follow-on

See [implementation and limits](79-external-methods-adoption.md), drawing on [Vaccaro](https://arxiv.org/abs/2606.11217). This follow-on does not change this document's historical registration or evidence claims.
