# Verified research outcomes in scoped episodic memory

`ResearchOutcomeMemory` connects the registered evidence-window study to NERVE's existing `MemoryGateway` and `TrustedMemoryLedger`. It stores a compact factual outcome, so a rejected experiment can become retrievable research evidence. It does not approve the rejected policy, award utility, train model weights or expand agent permissions.

## Proposal and review

A trusted host supplies a read/propose capability with no approval permission. The bridge revalidates the complete study receipt and predecessor chain, then proposes an episodic record containing only the protocol, canonical receipt hash, episode/step counts, gate outcome, selected candidate and evaluation-consumption flags. Raw sensor traces, filesystem paths and credentials are excluded. The content remains within the existing 2,048-character bound.

The record is pending and unavailable to agent retrieval. A separate host-issued read/approve capability calls `review`, which independently revalidates the source receipt, compares the pending record's exact bounded content and source hash, checks its durable proposal claim, and uses the gateway's existing approval method. Approval means **the recorded experiment outcome was verified**, not **the candidate succeeded**. No success score or adaptive-memory utility credit is assigned.

Existing scope, capability, revocation and deletion checks remain authoritative. The bridge is host-only local research code. It is not exposed as an untrusted-agent API, network authentication or clinical integration.

## Replay and failure handling

A scoped receipt claim is committed before proposal insertion. Claims use canonical parsed JSON identity, so whitespace/key-order changes cannot create new facts or bypass replay consumption. Raw bytes are still compared around source validation to detect concurrent changes.

Duplicate proposals are refused, including after record deletion. A failure remains consumed. An interruption after memory insertion but before recording the memory ID may leave an orphan pending row; it cannot be reviewed through this bridge or retrieved as approved evidence. There is no automatic retry/reconciliation for that partial write. The host can inspect/delete the pending row using existing administrative authority.

The claim tombstone retains scoped source-hash metadata after content deletion to prevent silent resurrection; this is not a claim of complete metadata erasure. All examples use synthetic research data and local unencrypted research SQLite storage.

## Executable integration

The demonstration script verifies the real completed evidence-window study, creates one pending outcome, checks that it cannot be retrieved, reviews it with a separate capability, and launches a fresh Python process with newly issued read authority to retrieve it from SQLite. It also attempts and rejects a cross-tenant read. The fresh process verifies persisted retrieval only; receipt verification occurs during proposal/review. No new plant episodes run.

```sh
cd /Users/aliyildirim/nerve-galahad
PYTHONPATH=src .venv/bin/python scripts/persist_research_outcome.py \
  --directory /private/tmp/nerve-research-memory-v1 \
  --study /private/tmp/nerve-evidence-window-study-v1 \
  --claims /private/tmp/nerve-evidence-window-study-claims.sqlite \
  --supervisor /private/tmp/nerve-research-supervisor-v1
# Existing demonstration directories are not overwritten. Read back separately:
PYTHONPATH=src .venv/bin/python scripts/persist_research_outcome.py \
  --directory /private/tmp/nerve-research-memory-v1 --verify-existing
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_research_outcome_memory.py -v
```

This provides reusable outcome memory. It does not yet make the research coordinator query those records while selecting future experiments, and it does not establish that retrieval improves downstream scientific discovery. That decision integration requires its own tests and measurements.

## Measured integration result

The actual synthetic demonstration passed: pending retrieval returned zero records; review approved one 569-character episodic fact; a fresh Python process retrieved exactly the same memory ID and `retain_baseline` recommendation; the cross-tenant read was denied. The stored outcome score is `NULL`. Independent read-only review checked the SQLite record, scoped claim, exact canonical content/source hash and real source receipt. No plant episodes ran and no candidate was promoted. [Integration report](evidence/research-memory-v1.json).

Final verification: **1,440 repository tests passed in 116.170 seconds**, with zero failures/errors. The 11 bridge tests cover canonical replay identity, snapshot changes, source failure, review authority, revocation, scope, restarts, deletion and interrupted proposal persistence. [Validation record](evidence/research-memory-validation.json).
