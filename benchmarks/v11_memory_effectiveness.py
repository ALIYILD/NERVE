"""Held-out synthetic NERVE episodic strategy retrieval experiment.

Compares utility-ranked memory versus most-recent history using exactly the
same 12 outcome observations per candidate. No LLM training is involved.
Synthetic rewards intentionally vary by context; this is not a general
agent capability or speedup claim.
"""
import json
import random
import statistics
import tempfile
from pathlib import Path

from nerve_awim.evolution_v01 import EvolutionMemory

SUCCESS_PROBABILITIES = {
    "brain": (.25, .72, .50),
    "sensor": (.65, .30, .48),
    "planning": (.45, .55, .83),
}


def episode(seed, *, training_trials=12, heldout_trials=180):
    if not 1 <= training_trials <= 100 or heldout_trials < 1:
        raise ValueError("invalid observation budgets")
    rng = random.Random(seed)
    strategies = {}
    with tempfile.TemporaryDirectory() as folder:
        memory = EvolutionMemory(Path(folder) / "experience.db")
        for context, probabilities in SUCCESS_PROBABILITIES.items():
            order = list(range(len(probabilities)))
            rng.shuffle(order)
            for index in order:
                successes = sum(rng.random() < probabilities[index]
                                for _ in range(training_trials))
                memory.record("agent", context, str(index),
                              successes / training_trials)
            # Both policies see the same history. The recency comparator
            # chooses the newest strategy regardless of outcome feedback.
            recent = order[-1]
            candidates = memory.select("agent", context, limit=len(probabilities))
            # Stable tie-breaking for reproducible seeded research (UUIDs
            # must never change the chosen strategy for equal utility).
            candidates = sorted(candidates,
                                key=lambda item: (-item.utility, int(item.outcome)))
            chosen = int(candidates[0].outcome)
            strategies[context] = (chosen, recent,
                                   max(range(len(probabilities)),
                                       key=lambda i: probabilities[i]))

        scores = {"outcome_memory": 0, "recency_memory": 0, "oracle": 0}
        heldout_rng = random.Random(seed + 100000)
        contexts = tuple(SUCCESS_PROBABILITIES)
        for t in range(heldout_trials):
            context = contexts[t % len(contexts)]
            selected, recent, oracle = strategies[context]
            probs = SUCCESS_PROBABILITIES[context]
            draw = heldout_rng.random()
            scores["outcome_memory"] += int(draw < probs[selected])
            scores["recency_memory"] += int(draw < probs[recent])
            scores["oracle"] += int(draw < probs[oracle])
    return {key: value / heldout_trials for key, value in scores.items()}


def benchmark(seeds=range(20)):
    rows = [episode(seed) for seed in seeds]
    if not rows:
        raise ValueError("nonempty seeds required")
    results = {key: statistics.mean(row[key] for row in rows)
               for key in rows[0]}
    margins = [row["outcome_memory"] - row["recency_memory"] for row in rows]
    return {
        "seeds": len(rows),
        "training_observations_per_context": 36,
        "heldout_trials_per_seed": 180,
        "success_rate": results,
        "mean_paired_margin": statistics.mean(margins),
        "memory_wins_seeds": sum(margin > 0 for margin in margins),
        "memory_ties_seeds": sum(margin == 0 for margin in margins),
        "limitations": "Synthetic known-context Bernoulli rewards; not demonstrated improvement in real agent tasks.",
    }


if __name__ == "__main__":
    print(json.dumps(benchmark(), indent=2, sort_keys=True))
