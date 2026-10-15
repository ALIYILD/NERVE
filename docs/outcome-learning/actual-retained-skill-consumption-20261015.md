# Actual retained skill v1 consumption

This follow-up is explicitly authorized by the user's `sign v3@7B` instruction.
It replaces the earlier synthetic fixture-only consumption demonstration with
verification of the actual retained registry artifact. It does not activate a
production policy or run inference. The separate historical 8/8 normalization
fixture remains selection among prewritten handlers, **not evidence of learning**;
the known best fixed handler also scores 8/8.

## Trust and evidence boundary

Galahad owns the registry entry, canonical scientific gate adapter, authorized
signing operation, and publication. The outcome lane only reads the resulting
record and artifacts through `load_selection_inputs(registry_directory)`, then
passes the exact bytes and host verifiers to the unchanged
`select_retained_skill` contract. No consumer code can sign a record.

The signer is a scoped local operator key acting under the user's explicit
instruction, not a claim that the user personally generated a cryptographic
signature. Private key material stays outside Git and outside the consumer.
The adapter independently pins authorized public-key material and scope; a key
asserted inside a candidate record is not trusted merely because it verifies
that record. See the Galahad signing record for the exact authorization and
trust-store provenance.

The real positive path checks the original scientific evidence bindings,
candidate configuration, deployed model digest, bank manifest and predecessor,
then uses the canonical gate adapter and authorized signature verifier. The
record is selected as a GoalOrchestrator leaf; a new process rereads and verifies
the actual registry and returns the same selection and persisted completed goal.
This is a retained-artifact consumption proof, not a new holdout evaluation.

## Negative-path coverage

The runner changes each of the actual development, holdout and bank-manifest
artifact bytes in memory; removes or corrupts the signature; substitutes an
unauthorized signer; changes configuration bytes, host model, host bank,
predecessor and signed version. Every rejected input must preserve the incumbent
and keep `production_authorized=false`. Source registry files and private keys
are not mutated. Additional false gate and revoked-authority callbacks exercise
consumer fail-closed behavior and are explicitly distinguished from the actual
positive-path verifiers.

The original six contract unit tests passed on the laptop in 0.236 seconds under
the user's new CPU-only authorization. Those tests deliberately use synthetic
HMAC fixtures; they are regression tests, **not** the real signed-entry proof.
The actual-artifact run completed successfully: **16/16 checks passed** in
98.86 seconds, with zero model calls and zero signing calls. The selected record
is `scientific-measurement-qwen2.5-coder-7b` version `v1`. The fresh process
reverified that selection and the persisted completed goal. Its public receipt is
[evidence/actual-retained-skill-consumer.json](evidence/actual-retained-skill-consumer.json).
After the interrupted session, the receipt’s adapter, consumer, record and three
evidence-artifact hashes were checked against this checkout and all matched.

## Reproduction

From this checkout, with the trusted Galahad adapter and its independently
installed trust store available:

```sh
PYTHONPATH=src python scripts/verify_retained_skill_consumption.py \
  --adapter /Users/aliyildirim/nerve-runpod-retention/scripts/retained_scientific_skill.py \
  --registry /Users/aliyildirim/nerve-runpod-retention/registry/scientific-v3-7b \
  --output docs/outcome-learning/evidence/actual-retained-skill-consumer.json
```

This runs CPU-only. The aggregate receipt records actual artifact hashes,
configuration/model/bank bindings, adapter and consumer hashes, each check's
result, wall time, and zero model/signing calls. Private trust-store material is
not included. No GPU or infrastructure action is part of this work.
