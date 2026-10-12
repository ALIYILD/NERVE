# Paired uncertainty smoke fixtures

`paired-conflicts-v1.json` contains 36 explicitly synthetic cases: 18 source-family pairs across operational, repository and synthetic-clinical predicates. Train, selection and sealed-final each contain six complete pairs; source-family names do not cross splits. Within a pair, task and initial source count are fixed and one value changes.

`manifest.json` freezes content SHA-256 and the pilot policy before comparisons. The evaluation module pins the manifest hash. Do not modify a consumed suite to tune a candidate; create a newly reviewed version for future promotion experiments.

These public fixtures provide deterministic conflict labels, not independent factual truth or blinded human labels. Shared boolean claim schemas limit semantic independence. The existing Hermes runtime uses a scripted fixture provider in all four arms. No live model-quality, medical-effectiveness or learned-improvement claim follows from the results.

Raw runtime evidence is written to the caller's controlled SQLite/output path, not this directory. See `docs/uncertainty/evaluation.md` for commands, denominators, omissions, confidence-interval caveats and release boundaries.
