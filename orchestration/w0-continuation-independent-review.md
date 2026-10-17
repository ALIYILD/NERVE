# W0 continuation: independent review checkpoint

Observed 2026-10-17 around 00:04 UTC. This is a checkpoint from a second session, not takeover of the live W0 coordinator. Existing pod locks and worker jobs were left untouched.

## Verified

- L2 coverage grid at b97aabf/doc129 is complete and must not be rerun; the shared ledger records the replacement task.
- Canonical signed v3 verifies. The independent reviewer checked all 80 baseline hashes, all 404 unsigned-payload evidence files, and all five payload-linked hashes without mismatches.
- L1 report records A40, Ollama0.40.5, pinned dae161e27b0e… digest, and10/10 dev identity matches. Five latency measurements fall in the explicitly registered band. Twelve physical calls are consistent with three deterministic/no-payload dev cases.
- MCP live inventory at this checkpoint: 5xndo7i7s5r9zn RUNNING under W2's B01b lock; the other five pods EXITED. The active pod is not an orphan.
- Nothing was signed, retained or activated by this review; registry/ and trust/ were read only.

## Open conditions for the active coordinator

1. Both fast-tier attempts timed out at180seconds. L1 is incomplete and merges remain blocked. B01b admission explicitly records fast-tier incomplete; do not describe it as completion of L1.
2. `scripts/overnight_conductor.py` is a one-shot policy checker. A live coordinator must actually invoke inventory/spend checks every10minutes, execute stop actions through MCP, and independently verify EXITED. The file alone does not establish overnight supervision.
3. Its call accounting covers identity and B-study claim roots only. Before admitting A, L4, L5 or another inference runner, register and include that runner's physical-attempt claims. Existing identity/B retries are counted correctly.
4. Per-pod retirement after two consecutive infrastructure failures is not implemented in the inspected checker. Track it explicitly before further admission; do not rely only on the night's total failure counter.
5. The requested original Desktop20261017 plan was not located by this session. The committed plan openly identifies itself as reconstructed. Doc130's exact replacement harmful-rate authority is not present in this session's user text; the primary coordinator must preserve the originating instruction rather than infer it from the generated document. Hash consistency is not evidence of that authority.

This report does not authorize any additional model calls, study, merge, signature, activation or budget. It supplements the active coordinator's ledger and is not a final L7/D1–D8 report.

## Follow-up at 00:08 UTC

The conductor now counts all `overnight-20261017-*` families plus explicitly registered absolute attempt roots, deduplicates claims, and preserves the prior total. It tracks per-pod consecutive failures, persists retirement and requests stop for a retired active pod without revoking the healthy pod's lock. Retirement stays sticky. Four focused temporary-fixture tests passed under the exclusive test lock, including the integrated lock/action path. Existing global stop thresholds are unchanged. These changes do not provide an autonomous scheduler.

B01b completed with35wins/0losses/65ties, both controls passed,100model calls, and offline replay verified. Verdict is dev-only `kept`. Independent MCP read confirmed5xndo7i7s5r9zn EXITED. Shared conductor at00:07:02 recorded all pods exited,112attempts and estimated compute$0.2084487305; storage excluded. The exclusive fast-tier retry also timed out at180seconds; no merge is justified by the focused tests.
