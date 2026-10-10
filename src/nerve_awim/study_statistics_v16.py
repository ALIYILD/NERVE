"""v1.6 paired-task evidence for NERVE Evolution agent evaluations.

Read-only scoring of already completed synthetic or live-plan evaluations.
Input records contain ONLY scored booleans, seed IDs and format labels,
never prompts, raw test cases, API keys or model-generated content.

McNemar's exact conditional p-value assumes independent discordant pairs:
because examples share seeds/tasks, treat it as descriptive only. A
seed-cluster bootstrap is reported only with >=5 distinct seed clusters.
"""
from collections import Counter, defaultdict
from math import comb, isfinite
from random import Random

KINDS = frozenset(("json_email", "plain_email"))


def _validate(records):
    values = tuple(records)
    if not values:
        raise ValueError("nonempty paired task results required")
    seen = set()
    for record in values:
        if type(record) is not dict or set(record) != {
                "seed", "format", "task_id", "no_memory", "with_memory",
                "no_memory_error", "with_memory_error"}:
            raise ValueError("unexpected paired result schema")
        if type(record["seed"]) is not int or not 0 <= record["seed"] <= 1000000:
            raise ValueError("invalid seed")
        if record["format"] not in KINDS:
            raise ValueError("unknown task format")
        if (type(record["task_id"]) is not str
                or not 0 < len(record["task_id"]) <= 64):
            raise ValueError("invalid anonymised task ID")
        if any(type(record[k]) is not bool for k in (
                "no_memory", "with_memory",
                "no_memory_error", "with_memory_error")):
            raise ValueError("paired outcomes must be boolean")
        key = (record["seed"], record["format"], record["task_id"])
        if key in seen:
            raise ValueError("duplicate paired task")
        seen.add(key)
    return values


def _simple(rows):
    n = len(rows)
    without = sum(row["no_memory"] for row in rows)
    with_mem = sum(row["with_memory"] for row in rows)
    gain = sum(row["with_memory"] and not row["no_memory"] for row in rows)
    loss = sum(row["no_memory"] and not row["with_memory"] for row in rows)
    return {
        "task_pairs": n,
        "no_memory_accuracy": without / n,
        "with_memory_accuracy": with_mem / n,
        "paired_accuracy_delta": (with_mem - without) / n,
        "memory_only_success": gain,
        "no_memory_only_success": loss,
        "both_success": sum(row["with_memory"] and row["no_memory"]
                            for row in rows),
        "both_fail": sum(not row["with_memory"] and not row["no_memory"]
                         for row in rows),
        "no_memory_task_errors": sum(row["no_memory_error"]
                                          for row in rows),
        "with_memory_task_errors": sum(row["with_memory_error"]
                                            for row in rows),
    }


def mcnemar_exact_p(better, worse):
    """Two-sided exact binomial conditional p-value, descriptive only."""
    if (type(better) is not int or type(worse) is not int
            or better < 0 or worse < 0):
        raise ValueError("nonnegative integer discordance counts required")
    n = better + worse
    if n == 0:
        return 1.0
    k = min(better, worse)
    # Conditional on discordances, null probability is 1/2.
    # Math.comb keeps this dependency-free; upper bound prevents
    # astronomically large intermediate integers on untrusted data.
    if n > 10000:
        raise ValueError("too many discordant pairs")
    probability = 2.0 * sum(comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, probability)


def seed_cluster_interval(records, *, repetitions=1000, confidence=.95):
    """Resample *seed clusters*, not individual task rows."""
    rows = _validate(records)
    if type(repetitions) is not int or not 100 <= repetitions <= 10000:
        raise ValueError("bootstrap repetitions must be 100..10000")
    if type(confidence) not in (int, float) or not isfinite(confidence) \
            or not .5 < confidence < 1:
        raise ValueError("invalid confidence")
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["seed"]].append(row)
    seeds = sorted(grouped)
    # With only a few clusters, percentile CIs are misleadingly precise.
    if len(seeds) < 5:
        return None
    rng = Random(1618033)
    estimates = []
    for _ in range(repetitions):
        chosen = [rng.choice(seeds) for _ in seeds]
        sampled = [r for seed in chosen for r in grouped[seed]]
        estimates.append(_simple(sampled)["paired_accuracy_delta"])
    estimates.sort()
    tail = (1 - confidence) / 2
    lo = max(0, min(len(estimates) - 1, int(tail * repetitions)))
    hi = max(0, min(len(estimates) - 1, int((1 - tail) * repetitions) - 1))
    return {
        "method": "seed_cluster_percentile_bootstrap",
        "confidence_level": float(confidence),
        "repetitions": repetitions,
        "lower": estimates[lo],
        "upper": estimates[hi],
        "distinct_seed_clusters": len(seeds),
    }


def summarize_pairs(records, *, bootstrap_repetitions=1000):
    rows = _validate(records)
    overall = _simple(rows)
    per_format = {
        label: _simple([row for row in rows if row["format"] == label])
        for label in sorted({row["format"] for row in rows})
    }
    exact = mcnemar_exact_p(
        overall["memory_only_success"], overall["no_memory_only_success"]
    )
    return {
        "overall": overall,
        "per_format": per_format,
        "seed_clusters": len({row["seed"] for row in rows}),
        "seed_cluster_delta_interval": seed_cluster_interval(
            rows, repetitions=bootstrap_repetitions
        ),
        "descriptive_mcnemar_exact_p": exact,
        "interpretation": (
            "Paired synthetic outcomes; p-value is descriptive only and "
            "does not adjust for within-seed or within-format dependence. "
            "At least five independent seed clusters are needed for a "
            "seed-level interval. No evidence of real LLM improvement "
            "without actual live-model experiments and larger heldout sets."
        ),
    }
