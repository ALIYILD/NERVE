# Bounded memory research

`memory_gateway/evaluation.py` implements `GatewayMemoryObjective` for the existing `recursive_evolution_v19.RecursiveEvolutionLoop`. There is no second optimiser. The existing frozen `RetrievalGenome` controls token/trigram weights in the existing deterministic scorer. Top-k, TTL, admission, quotas, cost thresholds and deployment controls are not evolved.

The objective builds eight public synthetic records through the gateway proposal/approval path. Every evaluation retrieves the same broad synthetic marker through the real gateway, then scores the approved text. A foreign-tenant read supplies the independent leakage count. Revoking its actor stops evaluation rather than yielding a synthetic success. Source identifiers preserve provenance.

The existing loop uses train and validation splits for bounded candidate selection, applies its absolute finite-score/isolation checks and records accepted/rejected lineage. It compares final selected and baseline holdout scores after selection. The objective permits only those two holdout evaluations and disallows further tuning on that instance. The fixture is publicly inspectable and can be overfit between runs; this is **not a sealed independent evaluator**. Operationally sealed holdout governance remains blocked for a later experiment.

The default executable study uses seed 19, three generations, four offspring per generation and patience three. These are loop budgets, not a subprocess timeout. All handlers are trusted local code. No generated source is executed, no weights trained, no policy deployed and no remote traffic initiated. A `candidate_for_human_review` result is only a research report; it does not grant promotion.

Run `PYTHONPATH=src python3 scripts/galahad_benchmark.py --samples 30`. The recorded fixture study evaluated 12 candidates across three generations; selected token/trigram weights 2/1, validation 6/6 versus baseline 4/6, and selected holdout 5/6. These small constructed results do not establish general retrieval improvement, inference speedup or clinical benefit. The full report preserves the baseline holdout and candidate lineage.

`tests/test_memory_gateway_evaluation.py` verifies real gateway isolation and capability revocation, single final comparison, closed post-holdout selection, rejected schemas, bounded reproducibility and research-only output. Four tests pass locally.
