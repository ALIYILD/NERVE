# Executable candidate routing

Registered scientific configurations now have an executable, bounded adapter.
`scientific_candidate_execution.py` prepares prompts and evidence, then either
returns a deterministic conflict abstention or invokes a host-supplied model
callback at most once. This is a hybrid rule/model pipeline, not weight learning.
The reviewed real-model transport mapping and efficacy study remain unfinished.

## Behavior and authority

The four registered configurations change prompt-template ordering, retrieval
count, an evidence-sufficiency instruction, or the conflict pre-step. Typed
configuration validation remains authoritative. Evidence is restricted to the
six host-prepared fields: content, source ID, version, current flag, timestamp
and content hash. Task answers, split, stratum and expected-output fields never
enter the prepared model request. A provenance hash checks content consistency;
it does not grant access or independently prove approval/currentness.

The host must retrieve approved scoped evidence and provide an authorization
callback that rechecks permissions and source validity. Execution calls it before
preparation, before dispatch and before releasing output. Input/configuration and
fixed-rule bindings are checked around callbacks; model payloads are copied and
mutation is rejected. Exceptions propagate without retries or fabricated outputs.
The existing gateway/inference re-retrieval pattern must be used by the eventual
network adapter; this module's callback boundary alone is not remote authentication.

The conflict pre-step recognizes the task bank's exact synthetic mass-question
syntax and a bounded numeric evidence grammar. Decimal comparison treats equivalent
numeric spellings equally. It scans every current record before retrieval top-k,
ignores stale records and values for other entities/measurements/units, and abstains
only for differing matching values. Unsupported queries or any unsupported current
evidence text select the ordinary model path. Recognized grammar does not imply
scientific truth or safe clinical interpretation.

Prepared prompts preserve evidence as untrusted data and request the generic
six-field JSON contract; they do not embed answer-specific enums. Model output
remains raw and unevaluated. Prompt instructions are not a guarantee of compliant
model behavior. Review flags do not themselves establish an approved clinical
workflow.

## Development-only route audit

`scientific_candidate_route_audit.py` revalidates candidate registration and the
current rejection screen before using only the task bank's development API. It
has no holdout gate capability. It sends only query and evidence into preparation;
development answers are used afterward to audit deterministic abstentions.

The audit measures routing, not model answers, efficacy, speed or cost savings.
It does not call `execute` or any inference service. The development bank has at
most two records per item, so retrieval limits four and eight cannot differ in
this audit. Larger synthetic unit fixtures separately verify that those limits
actually alter selection. Future efficacy studies need equivalent-capability
controls with the same deterministic conflict scan, to distinguish policy gains
from simply supplying a stronger parser.

All 700 development items share a narrow synthetic grammar across seven strata.
They are not a broad scientific-discovery benchmark. The holdout remains closed.

## Actual audit

The actual protected development bank produced 2,100 preparations over three
eligible configurations and 700 items. Conflict-check routing selected 100
deterministic abstentions, all consistent with development answers, and 600
model routes. The format and evidence-coverage configurations each selected 700
model routes. Those model routes were not executed; no full-answer accuracy
or performance comparison exists.

A fresh process prohibited inference, execution, holdout and seed access. Replay
preserved seven checked artifacts byte-for-byte with unchanged modification times,
including the development file/manifest and existing evidence journals.
[Actual audit](evidence/scientific-candidate-route-audit-v1.json) and
[restart verification](evidence/scientific-candidate-route-audit-v1-verification.json).

## Reproduction

```bash
PYTHONPATH=src .venv/bin/python scripts/audit_scientific_candidate_routes.py \
  --directory /Users/aliyildirim/nerve-research-runs/scientific-candidate-route-audit-v1 \
  --screen-directory /Users/aliyildirim/nerve-research-runs/scientific-candidate-screen-v1 \
  --bank-directory /Users/aliyildirim/nerve-research-runs/task-bank-v1 \
  --manifest-sha256 e11a17a72fb6482dc5978ee5e3c8d4b488f1d71d9c8e060aa382637020718ae6
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_scientific_candidate_execution.py' -v
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_scientific_candidate_route_audit.py' -v
.venv/bin/python scripts/verify_galahad.py baseline --timeout-seconds 600
```

Full regression: **1,944 tests passed in 170.928 seconds**, including 19 new
execution/route-audit tests. Independent review reran all 19 tests and verified
actual artifacts read-only. [Test evidence](evidence/scientific-candidate-execution-v1-tests.json).

## Remaining work

A reviewed model transport adapter, preregistered matched development experiment,
confidence intervals, sealed holdout and verified study adjudication remain next.
No new model improvement, complete self-improvement conductor, skill promotion,
weight training, clinical workflow or deployment is claimed. GPU endpoint/budget,
Galahad compatibility/licensing and durable restoration remain unverified. No
push, pull request or merge occurred.
