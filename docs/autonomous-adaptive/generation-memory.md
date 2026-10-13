# Bounded generation memory

`GenerationMemory` extends the existing `TrustedMemoryLedger` database and
`MemoryAuthority`. It adds no model, scheduler, approval issuer or network API.
The installed host entrypoint is `AgentOSLearning.generation_memory`.

Each scope binds profile, context, task family, task contract, runtime revision,
model revision, template revision and evaluator revision. Revisions are trusted
host inputs, not independent attestation of a provider alias. The scope has its
own hashed ledger context; old handoff lessons are not silently imported.

A note is explicitly labelled observation, failed attempt or hypothesis and
public or synthetic. Those classifications require host review; the inherited
secret-pattern check is not a general sensitive-data detector. No patient data,
credential files or arbitrary workspace paths belong in these requests.

## Host workflow

1. Propose bounded notes. They enter the existing ledger as **pending**.
2. Independently verify the source and use the existing ledger approval API with
   the exact scope evaluator revision. The generation CLI cannot approve notes.
3. Freeze up to eight approved notes into an immutable snapshot (16 KiB total).
   An optional parent is checked in the same scope. Lineage depth is at most 32.
4. Before a fresh session, retrieve the snapshot with `handoff`. All note and
   ancestor approvals, expiry, content integrity and scope are checked again.
   The snapshot confers no tool, provider, clinical or release authority.

The bridge exposes provider-free commands with an explicit profile and JSON file:

```sh
python3 scripts/agentos_bridge.py generation-propose --profile qa-release --task note.json
python3 scripts/agentos_bridge.py generation-freeze --profile qa-release --task snapshot.json
python3 scripts/agentos_bridge.py generation-inspect --profile qa-release --task lookup.json
python3 scripts/agentos_bridge.py generation-handoff --profile qa-release --task lookup.json
```

All inputs have a `scope` object with exactly the eight fields listed above.
`note.json` additionally contains `text`, `category`, `data_class`, `source_id`
and integer UTC epoch `valid_until`. `snapshot.json` additionally contains
`memory_ids`, `parent_id` (null for the first generation) and `valid_until`.
`lookup.json` additionally contains `snapshot_id`. Extra fields are rejected.
`inspect` returns metadata only; `handoff` explicitly returns approved advisory
notes. Neither command dispatches inference or alters the existing research budget.

## Evidence boundary

Tests exercise new-process persistence, pending-note rejection, ancestor
revocation/expiry, context/model/template drift, forged capabilities, immutable
snapshots, duplicate notes, modified content, CLI scope checks, metadata redaction
and unchanged native budgets/legacy recall. These are software checks, not a
measured learning result. Workspace artifacts, automatic generation execution,
runtime attestation and a matched fresh-start comparison remain outstanding.
