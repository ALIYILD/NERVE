# Family-B adapted study: prospective source freeze

The new versioned adapter, generator, independent truth validator, nine-stratum sealer and study harness passed all 18 focused tests in 19.442 seconds. Tests used mocked network responses and temporary bank fixtures: zero model calls, no research bank generated, no candidate designed and no holdout consumed.

The prospective protocol is `evidence/family-b-resumption-protocol-v1.json`. Exact implementation/test/protocol hashes and the test log hash are in `evidence/family-b-focused-verification.json`. Independent review checked preserved source ordering and names, independent ground truth, strict output decoding, exact dev-to-holdout candidate binding, shared attempt budget, and source integrity on replay.

This measures adapted v3 and adapted bootstrap pipelines. Parsing, capacity and preparation changes are explicit; it is not a bit-identical test of retained skill v1. All original protected paths remain unchanged. The actual bank must be independently validated and sealed before candidate design.

The separate full CPU preflight reached its registered 1,200-second limit without a completed result. This is not a pass. Complete CPU admission remains pending under a new prospective execution budget. The pod is EXITED while that work runs.

The original 17-test run is preserved in `evidence/family-b-focused-initial-verification.json` and its log. Before generation or inference, review tightened the prospective limits to L4 1,800 seconds and L6 2,400 seconds shared between candidate development and holdout. Holdout admission checks the remaining allowance before consuming slice 1. The 18-test rerun includes this regression.
