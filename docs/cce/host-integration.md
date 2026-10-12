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
bounded selection/holdout cycle with host-owned scope and profile. It takes the
same trusted discovery/provider/judge callbacks and explicit budgets as
`run_cue_cycle`; there is no callback import or execution from agent JSON. It
persists `cce-last-cycle.json` and exports candidate evidence to pending memory.
A cycle requires at least 30 holdout tasks before reservation or spending and
stops at rejection or pending operator approval. No live billing adapter is
installed for the currently unpinned OpenRouter worker, and no automatic scheduler
dispatch or activation is added.

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
