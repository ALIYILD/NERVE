"""Resume bounded NERVE research from revalidated, versioned recipe data."""
import argparse
import json

from nerve_awim.recursive_evolution_v19 import (
    RecursiveEvolutionLoop, SyntheticMemoryObjective,
)
from nerve_awim.research_checkpoint_v19 import (
    evaluator_fingerprint, load_checkpoint, write_checkpoint,
)


def previous_checkpoint(path):
    state = load_checkpoint(path)
    return state.selected, state.population


def run(*, checkpoint=None, seed=19, generations=6, checkpoint_out=None):
    state = load_checkpoint(checkpoint)
    objective = SyntheticMemoryObjective()
    try:
        result = RecursiveEvolutionLoop(
            objective=objective, generations=generations,
            seed=seed, offspring=4, patience=3,
        ).run(baseline=state.selected, previous_population=state.population)
        result["resumed_from_checkpoint"] = bool(state.population)
        result["checkpoint_reset_reason"] = state.reset_reason
        result["evaluator_fingerprint"] = evaluator_fingerprint()
        result["completed_runs"] = state.completed_runs + 1
        result["cumulative_candidates"] = (
            state.cumulative_candidates + result["candidates_evaluated"])
        result["run_seed"] = seed
        if checkpoint_out is not None:
            write_checkpoint(checkpoint_out, result)
        return result
    finally:
        objective.close()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", default=None)
    parser.add_argument("--checkpoint-out", default=None)
    parser.add_argument("--seed", type=int, default=19)
    parser.add_argument("--generations", type=int, default=6)
    args = parser.parse_args(argv)
    print(json.dumps(run(
        checkpoint=args.resume, checkpoint_out=args.checkpoint_out,
        seed=args.seed, generations=args.generations,
    ), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
