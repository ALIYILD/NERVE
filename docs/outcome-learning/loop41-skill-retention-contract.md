# Loop 41 retained-skill consumption contract

## Required first action after slice 2

**Validation update, 15 October 2026:** the user explicitly lifted the pause for
Runpod validation and development integration while keeping holdout and promotion
blocked. On exact commit `36339ac06e97ab3f0f4f264098d2985418b21de0`, all six retention
tests passed. The full suite ran once: 1,479 tests, two errors and 12 skips. Both
errors came from missing Git metadata in the source archive. After restoring the
real commit through a Git bundle, all three tests in the affected
`test_adaptation_evaluation.py` module passed, without source changes. The full
suite was not rerun or retrospectively relabeled as passing. Logs are preserved in
`/Users/aliyildirim/nerve-research-runs/runpod-validation-36339ac`.

Commands (executed on Runpod with `PYTHONPATH=src`):

```sh
.venv/bin/python -m unittest discover -s tests -p test_retained_skill_contract.py -v
timeout 1800 .venv/bin/python -m unittest discover -s tests -v
# After restoring the real Git commit metadata:
.venv/bin/python -m unittest discover -s tests -p test_adaptation_evaluation.py -v
```

The original instruction below is retained as history; the fixture-validation
prerequisite was addressed through the explicit Runpod exception above.

Wait for the user's explicit confirmation that slice 2 is finished. In the
first available validation window, run `tests/test_retained_skill_contract.py`
and the full NERVE test suite once, before any work builds on this contract.
Record the commands, commit tested and results in this document. If either
fails, resolve the failure before relying on the contract. These checks are
pending; this note does not authorize tests or inference during slice 2.

## Contract

Status: offline contract and fixture consumer only; no registry mutation, real
holdout access, promotion, or runtime activation. Loop 41's versioned skill
registry is the intended canonical store for retained skills; its live adapter
and signing authority still need implementation. Study stores remain canonical
for evidence. Orchestrator checkpoints contain references and selection receipts,
not a second skill registry. Loop 42 alone governs subsequent runtime activation.

The orchestrator consumes this immutable JSON record:

```json
{
  "skill_id": "namespace/stable-name",
  "version": "immutable-version",
  "config_hash": "sha256-of-exact-config-bytes",
  "evidence_bundle": {
    "dev_study": {"uri": "registry-relative-reference", "sha256": "64-lowercase-hex"},
    "holdout_study": {"uri": "registry-relative-reference", "sha256": "64-lowercase-hex"},
    "task_bank_manifest": {"uri": "registry-relative-reference", "sha256": "e11a17a72fb6482dc5978ee5e3c8d4b488f1d71d9c8e060aa382637020718ae6"},
    "model_digest": "d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668"
  },
  "supersedes": {"skill_id": "namespace/stable-name", "version": "incumbent-version", "config_hash": "64-lowercase-hex"},
  "signed_by": {"key_id": "trusted-promotion-authority", "signature": "detached-signature"}
}
```

`supersedes` is null only for a separately authorized first installation; this
replacement consumer requires an exact incumbent reference. Versions cannot be
reused. Hashes cover exact artifact bytes, not paths or JSON reserialization.
The signature covers UTF-8 JSON of the complete record excluding `signed_by`,
with sorted keys, compact separators, ASCII escaping and no non-finite numbers.
The trusted verifier must resolve the key independently, verify its signature,
and check current promotion authority for this skill and scope (including
revocation). A nonempty signer name is never authorization.

Selection order: freeze the record; check schema and predecessor; bind config,
model digest and goal's manifest digest; verify every evidence artifact against
its signed hash; ask Galahad's canonical gate adapter to verify the exact study
bytes and their candidate/config/model/manifest bindings and return a promotion
proposal; verify authorized promotion signature. Only then return the retained
version. Failure keeps the incumbent; the orchestrator must record failure and
must not rescore, weaken controls, infer a signature or silently activate it.
Dev `candidate_requires_review` alone is insufficient. The host must use bounded
read-only artifact resolution and must not resolve sealed references until
holdout access is explicitly authorized. The pure consumer has no filesystem,
network, inference, scorer, signing key, or registry-writing capability.

`src/nerve_awim/retained_skill_contract.py` is the opt-in reference consumer.
`tests/test_retained_skill_contract.py` connects it to a GoalOrchestrator leaf
using entirely synthetic byte fixtures and a test-only HMAC authority. Its gate
stub is not Galahad validation; production requires the real adapter and trusted
signature verifier. Tests were initially left unrun during the slice-2 machine
reservation and subsequently executed under the explicit Runpod exception above.
No actual holdout hash or promotion is asserted.
