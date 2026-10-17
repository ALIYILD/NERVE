# Signed evaluation handoff: proposed interface and current blocker

Status: design only. D7 remains partial. `Loop.evaluate(..., gate='signed')`
continues to refuse execution. This review made zero model calls, opened no
holdout data or private study journals, and changed no gate, registry or trust
files. No signature, activation or retention is requested or implied.

## What the existing APIs actually verify

`memory_gateway/retained_promotion_gate.py:verify()` verifies the canonical gate
signature against host trust, its payload, policy, source, evidence index and
protected manifest. It authenticates an installed **gate**, not an arbitrary
candidate, study receipt or outcome. `CanonicalProcess` executes the verified
gate source but its `update()` accepts caller-supplied Boolean scores. Feeding
fabricated scores through that class would not establish an authentic evaluation.

`scripts/run_v5_signed_gate_study.py:execute(replay=True)` is the existing
study-specific verification path. It binds registration to source hashes and
the canonical gate, checks private allocation and recorded model attempts,
recomputes scores and the terminal control checks, and compares the resulting
aggregate with the recorded result. It reads private allocation and item-level
journals and writes a replay receipt. Importing or invoking that path as a
generic SDK verifier would exceed this CPU review's no-holdout-read boundary.
Its fixed family-B v5/v4 candidate mapping, bank and filesystem paths also cannot
be substituted for the SDK's synthetic candidate registration.

## Proposed receipt-consumer contract

Keep evaluation in the authorized private custodian. A separate proposed API,
`accept_signed_evaluation(candidate, admission, receipt_bundle)`, would consume
an already completed assessment; it would not treat a public bank argument as
permission to allocate a sealed reserve. Implementation requires the following
host contract to be registered first:

1. A trusted admission record binds the exact SDK candidate registration hash
   to the scientific candidate source/configuration hashes, incumbent identity,
   domain/schema, model digest, study registration hash, bank manifest, gate
   payload and authorized custodian. Synthetic sandbox candidates have no such
   mapping today. File hashes supplied inside the bundle are insufficient to
   authenticate that mapping.
2. The custodian independently replays the private journal with network disabled
   and exports only the bound aggregate and verification attestation. It binds
   registration, allocation receipt, aggregate, journal index and replay source
   hashes, and includes all registered control outcomes. The host must specify
   an authenticated source for this attestation (for example, its existing
   trusted custodian service); a caller-supplied `verified: true` is not one.
   No new trust key or signing authority is created by this proposal.
3. The SDK invokes the existing canonical `verify()` without alternate roots,
   disabled loader checks or injected success callbacks. It compares the
   verified gate payload with admission and attestation, checks exact candidate
   and study identity and permitted terminal verdicts, then atomically stores
   the receipt. Duplicate identical receipts are idempotent; changed bytes for
   an existing study fail closed. Partial or failed replay cannot be promoted
   to a completed evaluation. Gate rejection/control mappings remain the
   registered custodian's responsibility and must be bound in its sources.
4. The result is labeled `receipt_consumed`, with the original assessment
   verdict and provenance. It never claims new evaluation, fresh reserve
   validity from hashes alone, canonical candidate status, or automatic
   promotion. `promote_proposal` remains a proposal; no routing, installation,
   retention, registry write or signature follows.

## Implementation admission and verification

The missing inputs are an authoritative candidate-to-study mapping and a
registered, authenticated custodian attestation contract. Neither follows from
the current `evaluate(candidate, bank, gate)` signature. Implementing a hash-only
receipt importer now would create an unsupported claim of signed assessment.

Once those inputs exist, focused tests must cover genuine bound receipt
consumption; changed registration, candidate, model, gate and aggregate hashes;
untrusted/self-hashed attestations; failed or incomplete replay; failed controls;
cross-domain substitution; duplicate and conflicting study receipts; and no
network, reserve access or registry/trust writes by the consumer. A positive
test must use the real canonical verifier and an authorized fixture of the
custodian contract, not a stub returning `verified: true`.

This documentation-only review did not run tests or acquire the shared test
lock. Runtime behavior is unchanged. Code inspection establishes the boundary;
it does not establish D7 completion.
