# Bounded memory research

`memory_gateway/evaluation.py` implements `GatewayMemoryObjective` for the existing `recursive_evolution_v19.RecursiveEvolutionLoop`. There is no second optimiser. The existing frozen `RetrievalGenome` controls token/trigram weights in the existing deterministic scorer. Top-k, TTL, admission, quotas, cost thresholds and deployment controls are not evolved.

The objective builds eight public synthetic records through the gateway proposal/approval path. Every evaluation retrieves the same broad synthetic marker through the real gateway, then scores the approved text. A foreign-tenant read supplies the independent leakage count. Revoking its actor stops evaluation rather than yielding a synthetic success. Source identifiers preserve provenance.

The existing loop uses train and validation splits for bounded candidate selection, applies its absolute finite-score/isolation checks and records accepted/rejected lineage. It compares final selected and baseline holdout scores after selection. The objective permits only those two holdout evaluations and disallows further tuning on that instance. The fixture is publicly inspectable and can be overfit between runs; this is **not a sealed independent evaluator**. Operationally sealed holdout governance remains blocked for a later experiment.

The default executable study uses seed 19, three generations, four offspring per generation and patience three. These are loop budgets, not a subprocess timeout. All handlers are trusted local code. No generated source is executed, no weights trained, no policy deployed and no remote traffic initiated. A `candidate_for_human_review` result is only a research report; it does not grant promotion.

Run `PYTHONPATH=src python3 scripts/galahad_benchmark.py --samples 30`. The recorded fixture study evaluated 12 candidates across three generations; selected token/trigram weights 2/1, validation 6/6 versus baseline 4/6, and selected holdout 5/6. These small constructed results do not establish general retrieval improvement, inference speedup or clinical benefit. The full report preserves the baseline holdout and candidate lineage.

`tests/test_memory_gateway_evaluation.py` verifies real gateway isolation and capability revocation, single final comparison, closed post-holdout selection, rejected schemas, bounded reproducibility and research-only output. Four tests pass locally.

## External one-use holdout

`memory_gateway/holdout.py` adds an offline host-reviewed external holdout, separate from the tuning loop. `freeze_holdout` reserves a study and canonical dataset digest together with typed selected/baseline genomes and scope. `evaluate_holdout` accepts no candidate overrides and consumes the claim transactionally **before reading the answer artifact**. A crash, malformed/tampered artifact, failed retrieval or failed evaluation burns the claim. Restarting the process does not restore a consumed study. Unique study/dataset constraints prevent reuse under a changed candidate, whitespace, case ordering or renamed study. The claim store allows at most 10,000 reservations.

The host-supplied UTF-8 JSON has exactly `version: 1`, `study_id` and `cases`. Each case has exactly `query` and `expected_source_id` (a source identifier or null for abstention). Payloads are bounded to 65,536 bytes, 100 distinct queries, 256 characters per query and 160 characters per answer identifier. Duplicate keys, extra fields and executable candidate schemas are rejected. No external URLs or code are executed. Answer-key content stays in the external artifact; reports contain aggregate selected/baseline hit counts, frozen weights and dataset digest only.

Both candidates score the identical gateway-retrieved approved record set with the existing `select` function and fixed `RetrievalGenome`. Retrieval authorisation is mandatory. Source identifiers must be unambiguous. This measures the lexical-prefiltered gateway plus scorer; it does not independently measure semantic coverage, clinical accuracy or KV speed. Freeze the selected candidate after tuning and ask the independent host to supply a fresh held-out artifact/digest; do not reuse this operation for candidate tuning.

The optional offline CLI exposes separate digest, freeze and evaluate operations:

```sh
# Independent host calculates a digest without copying its answer key into Git.
PYTHONPATH=src python3 scripts/galahad_holdout.py digest --artifact /external/holdout.json
# Replace DATASET_SHA256 with the host-provided digest; weights must already be frozen.
PYTHONPATH=src python3 scripts/galahad_holdout.py freeze --claims /external/claims.sqlite --study-id study1 --dataset-sha256 DATASET_SHA256 --selected 2 1
# Existing ledger must contain approved synthetic evidence in research/evaluation/synthetic.
PYTHONPATH=src python3 scripts/galahad_holdout.py evaluate --claims /external/claims.sqlite --study-id study1 --artifact /external/holdout.json --ledger /external/synthetic.sqlite
PYTHONPATH=src python3 -m unittest discover -s tests -p test_memory_holdout.py -v
```

The durable database and binding hashes provide crash/replay and accidental-corruption protection, **not cryptographic secrecy or malicious-host tamper resistance**. An operator can inspect the key, replace/delete the claim database, create new databases or rewrite both binding and digest. Protect these artifacts outside the agent workspace with separately governed operational controls. No production holdout or clinical data was evaluated; only temporary synthetic fixtures exercised this interface. No automatic promotion occurs, even if selected scores improve. Formal independent dataset custody remains an operational requirement.

Scope metadata is checked before consumption: an independently authorised caller in another scope cannot burn a frozen claim. The rightful scope can still evaluate it afterward. The evaluate CLI rejects both `--selected` and `--baseline` overrides instead of ignoring them. Twelve holdout tests cover these boundaries in addition to durable replay and corruption handling.
