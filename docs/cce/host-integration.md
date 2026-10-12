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
python3 scripts/agentos_bridge.py cce-demo --state /tmp/nerve-cce-demo-state
python3 scripts/agentos_bridge.py cce-inspect --profile qa-release --cue-candidate CANDIDATE_ID
python3 scripts/agentos_bridge.py cce-revoke --profile qa-release --cue-candidate CANDIDATE_ID --cue-review REVIEW_ID
```

Status and inspection do not invoke a provider. The demo is synthetic and cannot
activate a cue. The ordinary bridge `status` includes `cognitive_cues`; CCE commands
also write `cce-status.json` within the selected existing host state directory.

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
