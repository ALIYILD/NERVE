# Staged external-methods integration

`scripts/reconcile_external_methods.py` adds a GoalOrchestrator task that delegates
the retrospective v3 development audit to Galahad's separate evaluator process.
The registration pins source hashes and both input files. Successful completion
means the audit is complete, not that promotion or clinical efficacy is established.

```sh
/Users/aliyildirim/nerve-galahad/.venv/bin/python scripts/reconcile_external_methods.py \
  --galahad /Users/aliyildirim/nerve-galahad \
  --state /private/tmp/nerve-external-methods-goal \
  --receipt /Users/aliyildirim/nerve-galahad/docs/galahad/evidence/scientific-candidate-v3-study.json \
  --development /Users/aliyildirim/nerve-research-runs/task-bank-v1/dev.json
```

All new inference, holdout access and production promotion are disabled. The
historical `reconcile_tier6_goal.py` registration and verifier remain unchanged.
Galahad's `docs/galahad/79-external-methods-adoption.md` documents the implementation,
statistical limits, source citations, tests and remaining live-evaluation gates.

The independent-evaluation and typed-repair design follows
[Regimes](https://arxiv.org/abs/2606.10241); pre-call registration follows
[Vaccaro](https://arxiv.org/abs/2606.11217). This bridge does not authorize the
generator to change the verifier, wallet, scorer, signatures or protected files.
