# NERVE AutoResearch: first integration

This prototype adapts the idea of a fixed, machine-judged experiment loop, not the code of Karpathy's training system.

**Run**:
```bash
PYTHONPATH=src python -m nerve_awim.autoresearch_v01
```

It tests four predefined learning-rate candidates, selects only on validation error, and reports performance on untouched seeds once. The ledger writer can record each decision in local JSONL.

## To become a true autonomous research coordinator
1. Use a restricted, sandboxed candidate patch protocol with strict file allowlists.
2. Enforce CPU/memory/time budgets in the execution environment, not solely in a prompt.
3. Build agent roles for hypothesis proposal, benchmark checking and independent review.
4. Separate validation data from a final private evaluation dataset.
5. Compare predictive MAE alongside goal error, safety constraints, latency and cost.
6. Require explicit approval before merging candidate changes to production.

Do not claim autonomous source-code self-improvement, continuous background experimentation, or empirical performance improvement beyond the synthetic test until those capabilities are implemented and measured.
