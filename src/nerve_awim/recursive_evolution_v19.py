"""NERVE v1.9: AlphaEvolve-inspired *data-only* recursive research evolution.

Every generation: propose bounded retrieval-weight mutations -> evaluate on
fixed training and validation queries -> gate regression/scope failures ->
retain the best evaluated genome -> repeat. An independent holdout is used
only once AFTER final selection. No Python/program mutations, network calls,
model-weight training, policy changes, automated merges or device control.

This is a local deterministic research loop, NOT Google AlphaEvolve.
"""
from dataclasses import asdict, dataclass
from math import isfinite
from pathlib import Path
from random import Random
from typing import Callable
import json
import re
import tempfile

from .memory_v18 import MemoryAuthority, TrustedMemoryLedger

TOKENS = re.compile(r"[a-z0-9]+")
DOCS = {
    "calibration": "optical light sensor calibration",
    "sorting": "integer numeric sorting algorithm",
    "retrieval": "bibliography citations evidence documents",
    "movement": "robot locomotion controller",
    "imaging": "cortical EEG brain imaging",
    "noise1": "calendar reminders and meetings",
    "noise2": "sensor reading reminder",
    "noise3": "integer addition practice",
}
TRAIN = (
    ("calibrate optical sensors", "calibration"),
    ("sort integers", "sorting"),
    ("cite documents", "retrieval"),
    ("locomotor controller", "movement"),
    ("brain scan imagery", "imaging"),
    ("daily calendar", "noise1"),
)
VALIDATION = (
    ("optics calibration", "calibration"),
    ("numerical sort", "sorting"),
    ("reference citation", "retrieval"),
    ("robot movement", "movement"),
    ("cortex imaging", "imaging"),
    ("meeting reminders", "noise1"),
)
HOLDOUT = (
    ("sensor calibration", "calibration"),
    ("integer arrangement", "sorting"),
    ("document citation", "retrieval"),
    ("locomotion robot", "movement"),
    ("cortical brain imaging", "imaging"),
    ("schedule calendar", "noise1"),
)
# Dataset is constructed and known to trusted evaluator, not a benchmark of
# real embeddings or an LLM. Evaluator function is not mutated.
DATASETS = {"train": TRAIN, "validation": VALIDATION, "holdout": HOLDOUT}


def grams(text):
    value = " ".join(TOKENS.findall(text.lower()))
    return {value[i:i+3] for i in range(max(0, len(value)-2))}


def select(query, documents, genome):
    """Fixed, transparent token/trigram scorer; genome changes weights only."""
    query_words = set(TOKENS.findall(query.lower()))
    query_grams = grams(query)
    scored = []
    for identifier, content in documents.items():
        words = set(TOKENS.findall(content.lower()))
        chunks = grams(content)
        unigram = len(query_words & words) / max(1, len(query_words))
        trigram = len(query_grams & chunks) / max(1, len(query_grams))
        score = genome.token_weight * unigram + genome.trigram_weight * trigram
        if score > .000001:
            scored.append((score, identifier))
    # Score > 0 prevents arbitrary fallback when there is no evidence.
    if not scored:
        return None
    # Lexicographic tie-break to make seed-independent ordering stable.
    return min(scored, key=lambda item: (-item[0], item[1]))[1]


@dataclass(frozen=True)
class RetrievalGenome:
    token_weight: int = 3
    trigram_weight: int = 0

    def __post_init__(self):
        if type(self.token_weight) is not int or not 0 <= self.token_weight <= 5:
            raise ValueError("token weight must be 0..5")
        if (type(self.trigram_weight) is not int
                or not 0 <= self.trigram_weight <= 5):
            raise ValueError("trigram weight must be 0..5")
        if self.token_weight + self.trigram_weight < 1:
            raise ValueError("retrieval scoring requires at least one feature")


@dataclass(frozen=True)
class EvalScore:
    accuracy: float
    hits: int
    queries: int
    cross_tenant_leaks: int


class SyntheticMemoryObjective:
    """The memory ledger is the independent approved, scoped source of truth."""

    def __init__(self):
        self._temporary = tempfile.TemporaryDirectory()
        authority = MemoryAuthority()
        self.writer = authority.issue("research", "agent", permissions=("propose", "read"))
        self.reviewer = authority.issue("research", "agent",
                                        permissions=("approve", "read"))
        self.other_tenant = authority.issue("foreign", "agent", permissions=("read",))
        self.ledger = TrustedMemoryLedger(
            Path(self._temporary.name) / "recursion.sqlite", authority
        )
        self.ids = {}
        for name, content in DOCS.items():
            mid = self.ledger.propose(
                self.writer, context="research", content=content,
                source_id="synthetic-source-" + name)
            self.ledger.decide(
                self.reviewer, mid, approve=True,
                evaluator_id="frozen-deterministic-fixture", score=1.0)
            self.ids[mid] = name

    def close(self):
        self._temporary.cleanup()

    def evaluate(self, genome, split):
        if not isinstance(genome, RetrievalGenome) or split not in DATASETS:
            raise ValueError("only typed recipes and fixed splits are supported")
        approved = self.ledger.approved_pool(
            self.writer, context="research", limit=100
        )
        corpus = {self.ids[m.memory_id]: m.content for m in approved}
        foreign = self.ledger.approved_pool(
            self.other_tenant, context="research", limit=100
        )
        leaks = len(foreign)
        correct = sum(
            select(query, corpus, genome) == label
            for query, label in DATASETS[split]
        )
        return EvalScore(correct / len(DATASETS[split]),
                         correct, len(DATASETS[split]), leaks)


class RecursiveEvolutionLoop:
    """Fail-closed bounded controller: no evaluator/threshold self-modification."""

    def __init__(self, *, objective, generations=6, offspring=4,
                 seed=19, patience=3, mutation=None):
        if not callable(getattr(objective, "evaluate", None)):
            raise TypeError("independent evaluator required")
        for name, value, lower, upper in (
            ("generations", generations, 1, 12),
            ("offspring", offspring, 1, 6),
            ("patience", patience, 1, 12),
        ):
            if type(value) is not int or not lower <= value <= upper:
                raise ValueError("invalid research budget: " + name)
        if type(seed) is not int or not 0 <= seed < 2**32:
            raise ValueError("invalid reproducibility seed")
        if mutation is not None and not callable(mutation):
            raise TypeError("mutation must be trusted code")
        self.objective = objective
        self.generations = generations
        self.offspring = offspring
        self.seed = seed
        self.patience = patience
        self.mutation = mutation or self._mutate

    @staticmethod
    def _mutate(parent, rng):
        directions = ((0, 1), (-1, 1), (1, 0), (0, -1), (1, -1))
        d_token, d_tri = directions[rng.randrange(len(directions))]
        token = min(5, max(0, parent.token_weight + d_token))
        tri = min(5, max(0, parent.trigram_weight + d_tri))
        if token + tri < 1:
            token = 1
        return RetrievalGenome(token, tri)

    @staticmethod
    def _safe(score):
        return (type(score) is EvalScore
                and type(score.accuracy) is float and isfinite(score.accuracy)
                and 0 <= score.accuracy <= 1
                and type(score.cross_tenant_leaks) is int
                and score.cross_tenant_leaks == 0
                and type(score.hits) is int
                and type(score.queries) is int
                and 0 <= score.hits <= score.queries and score.queries > 0)

    def run(self, *, baseline=RetrievalGenome()):
        if type(baseline) is not RetrievalGenome:
            raise TypeError("trusted baseline recipe required")
        rng = Random(self.seed)
        best = baseline
        score = self.objective.evaluate(best, "validation")
        training = self.objective.evaluate(best, "train")
        if not self._safe(score) or not self._safe(training):
            raise RuntimeError("baseline failed independent research safety gates")
        base_score = score
        seen = {best}
        records = []
        stale = 0
        for generation in range(1, self.generations + 1):
            pool = []
            # Even after all recipes have been exhausted, stop rather than
            # unboundedly mutate or rerun the same candidate forever.
            for _ in range(self.offspring * 6):
                candidate = self.mutation(best, rng)
                if type(candidate) is not RetrievalGenome:
                    raise TypeError("untrusted mutation produced invalid genome")
                if candidate in seen:
                    continue
                seen.add(candidate)
                pool.append(candidate)
                if len(pool) >= self.offspring:
                    break
            if not pool:
                records.append({"generation": generation, "stop": "search_space_exhausted"})
                break
            evaluated = []
            for candidate in pool:
                tr = self.objective.evaluate(candidate, "train")
                val = self.objective.evaluate(candidate, "validation")
                eligible = (self._safe(tr) and self._safe(val)
                            and tr.accuracy >= training.accuracy
                            and val.accuracy > score.accuracy + 1e-12)
                evaluated.append((candidate, tr, val, eligible))
            eligible_rows = [x for x in evaluated if x[3]]
            winner = max(eligible_rows,
                         key=lambda x: (x[2].accuracy, x[1].accuracy,
                                        -x[0].trigram_weight,
                                        -x[0].token_weight)) if eligible_rows else None
            records.append({
                "generation": generation,
                "parent": asdict(best),
                "evaluated": [
                    {"genome": asdict(g), "training": asdict(tr),
                     "validation": asdict(val),
                     "accepted": g == winner[0] if winner else False,
                     "candidate_for_selection": eligible}
                    for g, tr, val, eligible in evaluated
                ],
                "selection": "improved" if winner else "no_eligible_improvement",
            })
            if winner:
                best, training, score = winner[:3]
                # winner[:3] holds genome, TRAINING and VALIDATION.
                stale = 0
            else:
                stale += 1
            if stale >= self.patience:
                break
        # Holdout is measured once, after selection; selection never uses it.
        holdout = self.objective.evaluate(best, "holdout")
        baseline_holdout = self.objective.evaluate(baseline, "holdout")
        if not self._safe(holdout) or not self._safe(baseline_holdout):
            raise RuntimeError("holdout failed independent scope/safety checks")
        holdout_ok = holdout.accuracy >= baseline_holdout.accuracy
        return {
            "status": "candidate_for_human_review" if (
                score.accuracy > base_score.accuracy and holdout_ok
            ) else "no_verified_improvement",
            "baseline": asdict(baseline),
            "selected": asdict(best),
            "baseline_validation": asdict(base_score),
            "selected_validation": asdict(score),
            "baseline_holdout": asdict(baseline_holdout),
            "report_only_holdout": asdict(holdout),
            "generations_run": len(records),
            "candidates_evaluated": len(seen) - 1,
            "lineage": records,
            "retained_learning": "best evaluated data-only recipe across generations",
            "safety": "No source edits, secret keys, network calls or deployment; \
all promotions require independent external human approval.",
            "limitations": "Constructed retrieval dataset and data-only mutations. \
Not autonomous AlphaEvolve, not general intelligence or proven speedup.",
        }


def demo(generations=6, seed=19):
    objective = SyntheticMemoryObjective()
    try:
        return RecursiveEvolutionLoop(
            objective=objective, generations=generations, seed=seed
        ).run()
    finally:
        objective.close()


if __name__ == "__main__":
    print(json.dumps(demo(), indent=2, sort_keys=True))
