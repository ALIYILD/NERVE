"""Safe resume runner for bounded recursive NERVE research.

Reads a previous report as untrusted structured data. Only bounded integer
genomes are reconstituted; previous scores, authorisations, code, or policy
values are NEVER trusted. Re-evaluates prior selection on new local ledger.
"""
import argparse
import json
from pathlib import Path

from nerve_awim.recursive_evolution_v19 import (
    RecursiveEvolutionLoop, RetrievalGenome, SyntheticMemoryObjective,
)


def previous_checkpoint(path):
    if path is None:
        return RetrievalGenome(), ()
    file = Path(path)
    if not file.exists():
        return RetrievalGenome(), ()
    if file.stat().st_size > 250000:
        raise ValueError("untrusted research checkpoint oversized")
    data = json.loads(file.read_text(encoding="utf-8"))
    if (type(data) is not dict or data.get("study_protocol")
            != "nerve-recursive-data-only-v19"):
        raise ValueError("invalid checkpoint protocol")
    approved_fields = {"token_weight", "trigram_weight"}
    def read_genome(value):
        if type(value) is not dict or set(value) != approved_fields:
            raise ValueError("unexpected checkpoint genome fields")
        return RetrievalGenome(**value)
    previous = read_genome(data.get("selected"))
    archive = data.get("population_archive")
    if type(archive) is not list or len(archive) > 36:
        raise ValueError("invalid checkpoint archive")
    known = tuple(read_genome(x) for x in archive)
    if previous not in known:
        raise ValueError("checkpoint selected genome absent from archive")
    # Don't trust persisted historical validation or holdout metrics.
    return previous, known


def run(*, checkpoint=None, seed=19, generations=6):
    parent, archived = previous_checkpoint(checkpoint)
    objective = SyntheticMemoryObjective()
    try:
        result = RecursiveEvolutionLoop(
            objective=objective, generations=generations,
            seed=seed, offspring=4, patience=3,
        ).run(baseline=parent, previous_population=archived)
        result["resumed_from_checkpoint"] = bool(archived)
        result["run_seed"] = seed
        return result
    finally:
        objective.close()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", default=None)
    parser.add_argument("--seed", type=int, default=19)
    parser.add_argument("--generations", type=int, default=6)
    args = parser.parse_args(argv)
    print(json.dumps(run(
        checkpoint=args.resume,
        seed=args.seed,
        generations=args.generations,
    ), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
