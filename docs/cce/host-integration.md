# Installed NERVE host wiring

The existing installed path is now connected end to end:

`Agent OS bridge run → CueHost → governed CCE selection → native Hermes worker → worker receipt → independent handoff judgment → feedback and pending memory`

The existing scheduler invokes `nerve-review/scripts/agentos_bridge.py`; it does
not use the optional `HermesAgentRuntime` wrapper. CCE therefore has both a library
integration and a direct worker integration. No separate scheduler, installed
Hermes checkout modification or competing agent runtime is required.

## Operator commands

```bash
python3 scripts/agentos_bridge.py cce-status
python3 scripts/agentos_bridge.py cce-status --profile qa-release
python3 scripts/agentos_bridge.py cce-profile --profile qa-release
python3 scripts/agentos_bridge.py cce-demo --state /tmp/nerve-cce-demo-state
python3 scripts/agentos_bridge.py cce-inspect --profile qa-release --cue-candidate CANDIDATE_ID
python3 scripts/agentos_bridge.py cce-route --profile qa-release
python3 scripts/agentos_bridge.py cce-dataset-status --profile qa-release
python3 scripts/agentos_bridge.py cce-job-status
python3 scripts/agentos_bridge.py cce-job-cancel --cue-job JOB_ID
python3 scripts/agentos_bridge.py cce-job-submit --task /path/to/cce-job.json
python3 scripts/agentos_bridge.py cce-readiness --profile qa-release --cue-candidate CANDIDATE_ID
python3 scripts/agentos_bridge.py cce-approve --profile qa-release --cue-candidate CANDIDATE_ID --cue-generation 0 --cue-review REVIEW_ID --cue-valid-for 86400
python3 scripts/agentos_bridge.py cce-revoke --profile qa-release --cue-candidate CANDIDATE_ID --cue-review REVIEW_ID
```

Status and inspection do not invoke a provider. The demo is synthetic and cannot
activate a cue. The ordinary bridge `status` includes `cognitive_cues`; CCE commands
also write `cce-status.json` within the selected existing host state directory.

`cce-profile` skips the provider catalog and credentials entirely. It records the
installed Hermes revision and rendered baseline template hash, with unknown model
and tokenizer identities represented as null. It performs zero model calls and
writes `cce-last-profile.json`. The observed `qa-release` installation on 2026-10-12
used `qwen/qwen3.8-27b:free`, Hermes revision
`64ad33e32dadbdb462468c7384aa38e5c99a1b7a`, and a clean Hermes checkout. Its model and
tokenizer attestation remained unavailable. This is a local installation snapshot,
not a provider availability or model-performance claim.

`cce-route` returns the current generation for explicit compare-and-swap approval.
The generation in the example is illustrative; use the observed value. Approval
requires independently passed, unexpired evidence and the currently configured
exact profile. This trusted local operator command is not exposed to the worker
or candidate generator. It cannot grant provider, tool or clinician permission.
`cce-readiness` recomputes report eligibility and stores `cce-last-readiness.json`.
It always returns `authorization_granted: false`; missing live staging and rollback
receipts stay visible. CLI callers cannot upload assertions to satisfy those gates.

## Trusted research callbacks

The existing host can call `CueHost.discover(...)` to collect bounded proposals
through the existing Hermes role. Paper imports preserve their source locator,
revision, original model and injection mode as unverified provenance. Exact-content
duplicates and unsupported modes produce rejection receipts. Collection neither
registers nor activates cues. The callback host still enforces billing, output-token
limits, timeout and retries; call-count bounds alone are not a billing guarantee.

`CueHost.run_cycle(profile, permission_granted=True, ...)` invokes the existing
bounded selection/regression/holdout cycle with host-owned scope and profile. It takes the
same trusted discovery/provider/judge callbacks and explicit budgets as
`run_cue_cycle`; there is no callback import or execution from agent JSON. It
persists `cce-last-cycle.json` and exports candidate evidence to pending memory.
A cycle requires at least 30 holdout tasks before reservation or spending and
stops at rejection or pending operator approval. No live billing adapter is
installed for the currently unpinned OpenRouter worker. Durable jobs can enter the
existing scheduled loop, but they wait without dispatch until the host supplies a
trusted adapter. Scheduling never activates a candidate.

Use `CueHost.run_dataset_cycle(...)` for content-bound research. Its first durable
dataset reservation upgrades the scope, prevents ID-only downgrade and stops
legacy candidates from being served or newly approved. Fresh dataset-bound
evidence is then required. See [reservation and migration rules](local-research.md#durable-research-reservations).
`cce-dataset-status` reports scoped counts without bootstrapping the cue engine.

## Configuration and approval

An absent `cce-config.json` means off. The checked-in
[`configs/cce.example.json`](../../configs/cce.example.json) explicitly disables
CCE with an empty profile map. Each configured entry must contain exactly a
complete `model_profile` and `task_type: "handoff"`. Native host profiles support
instruction mode only. Missing/ambiguous revisions, unknown fields and unsupported
contexts are rejected.

Setting `enabled` does not approve a cue. Existing host capabilities, preregistered
experiments, independent evaluation, operator approval and expiry remain required.
`CueHost` stores adjunct records in the same Agent OS `learning.sqlite3`, under the
`agentos-local` tenant and exact installed profile scope. It introduces no separate
inference or release authority. The same adapter exposes inspected feedback and
pending memory export to trusted host code.

## Actual execution boundary

Only operational bridge `run` requests the fixed low-risk evidence-handoff cue
context. Probe, discovery, scheduled research and both study comparison arms remain
uncued by default. This prevents an active operational cue from contaminating the
no-cue baseline or discovering its own apparent improvement.

The native worker validates the selected envelope after resolving the actual
available model and installed SOUL. Its template identity hashes the original
system message. Changed model/SOUL/template, unsupported prefix mode, expired
approval or missing worker attestation yields the unchanged baseline. The original
text-only/no-tools, no-memory-write, retry, timeout and free-provider constraints
remain intact.

**Current live limitation:** OpenRouter `:free` aliases do not expose immutable
weight and tokenizer revisions in this worker. The production worker therefore
cannot attest a cue profile and returns `provider_revision_unavailable` for an
otherwise valid envelope. It never trusts a request/config flag as proof. A future
provider adapter must obtain that identity independently. This limitation is
deliberate; wiring is present, but unverified cue application remains disabled.

The host records `latest-cce-native.json` with separate selection and application
receipts. A prepared envelope is not counted as applied. Feedback runs only when
the worker confirms application and the existing host observation is fresh.
Independent handoff judgment can revoke a failing cue. Memory exports stay pending;
duplicate observations create neither duplicate feedback nor duplicate memory.
Raw cue text, task text and credentials are not written into these receipts.

## Integration scope

The CCE change preserves pre-existing uncommitted ARC/adaptation work in the main
checkout. Those unrelated changes are not part of the CCE publication. Research
GPU reproduction, eligible live evidence and clinical/staging deployment remain
the separate gates documented in the [verification ledger](verification.md).

Schema 2 datasets add a required retained-capability regression partition. The
host passes its frozen tasks into the same cycle; callers cannot override them.
After a scope reserves its first regression study, the coordinator requires a
persisted passing regression gate before holdout evaluation, approval or serving.
`cce-inspect` includes the scoped requirement and stored evaluation;
`cce-readiness` recomputes the gate and exports its digest and decision only.
See [retained-capability screening](local-research.md#retained-capability-screening)
for the criteria and limitations. This is opt-in research infrastructure, with no
new scheduler or automatic production activation.

## Durable jobs in the existing scheduled loop

`agentos_cue_jobs` stores immutable CCE job specifications in the existing
`autoresearch.sqlite3`, with outcomes in its existing event ledger. The bridge's
`cycle` command and `agentos_autoresearch.tick` supply scheduling and the existing
host lock. There is no additional service or scheduler. `cce-job-submit --task`
admits a bounded frozen specification; `cce-job-status` exposes redacted job state.
Submission requires an already configured exact profile; that profile may be
disabled while the job is queued. Submission grants neither cue approval nor
operational activation.

Host code supplies the trusted adapter registry. A JSON adapter identifier cannot
import a Python module, select an arbitrary callback, or execute supplied code.
The installed registry is empty by default: jobs remain pending when no matching
adapter is installed. Disabled CCE configuration or a mismatched profile also
prevents dispatch. A ready tick claims at most one job before executing its
bounded dataset cycle. Interrupted running work is sealed without replay; exposed
evaluation content is never retried automatically.

The scheduled path requires a frozen schema 2 dataset with at least 30 holdout
tasks. One discovery call, one paired selection task, one paired regression task
and 30 paired holdout tasks require at least 65 calls. The native Hermes bridge's
20-call daily limit cannot fund that cycle. Its current response also lacks exact
model/tokenizer attestation, complete CCE usage/billing receipts and answer
confidence. Host adapters must preserve existing call ledgers and enforce the
full budget; scheduling does not waive those requirements. Missing confidence
cannot be filled with a grader's correctness verdict or a constant probability.

Existing autoresearch audit bundles cannot be silently relabeled as handoff
benchmarks. `CueHost` owns the low-risk handoff classification, while dataset
curation and independent grading remain explicit host responsibilities. A
qualifying cycle ends at pending operator approval and pending memory export.

### Exact job specification

`--task` reads a bounded regular UTF-8 JSON file (at most 5 MiB). Duplicate keys,
nonfinite numbers and additional fields are rejected. The object contains exactly:

| Field | Required value |
| --- | --- |
| `job_id`, `profile` | Unique job identifier and configured host profile name |
| `dataset` | Complete frozen schema 2 dataset object, including all four partitions |
| `model` | Complete `ModelParity` object for the configured profile |
| `generator_id`, `evaluator_id` | Explicit separate discovery and evaluation identities |
| `adapter_id`, `adapter_revision` | Identifier and exact revision of a trusted host registry entry |
| `max_calls` | Bounded integer covering discovery and every paired task |
| `max_cost_usd` | Total research budget |
| `discovery_cost_cap_usd` | Maximum discovery fee |
| `per_call_cost_cap_usd` | Maximum fee per evaluation request |
| `permission_granted` | Literal `true` for the bounded research job |

`model` contains exactly `provider`, `model`, `revision`, `tokenizer`,
`tokenizer_revision`, `template_digest`, `sampling_digest`, `temperature`,
`max_tokens`, `context_digest`, and `profile_key`. These values must describe the
actual trusted transport; a submission cannot manufacture provider attestation.
The complete dataset schema is specified in `cue_dataset.py`. Expected answers
remain in the local job specification and trusted grader, not discovery input or
redacted status. Do not put credentials in a job specification.

A host registry entry contains `revision`, `discovery_execute`, `provider`,
`judge`, and `preflight`. The callable `preflight(host, admission)` must return
literal `True` before claim. It receives model/profile identity, dataset digest
and budgets, without task content, and must check durable daily/provider budget
availability without inference. Missing preflight, failure or a non-true result
leaves the job waiting. Both existing autoresearch configuration and CCE must be
enabled; a queued job cannot enable either.

`cce-job-cancel --cue-job JOB_ID` changes a pending job to `cancelled`. It does
not delete its immutable specification, reset evidence reservations or requeue
the job. Running or completed work cannot be cancelled through this command.

Queued CCE work takes priority over ordinary audit research. A waiting CCE job
suppresses unrelated audit dispatch for that tick; cancel the pending job to
resume audit work. The queue accepts at most 32 pending/running jobs and reports
the latest 64 jobs. Its nested dataset remains subject to the 4 MiB dataset cap.
