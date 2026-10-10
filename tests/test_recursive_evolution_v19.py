"""Independent gates, repeated mutation, stop budgets, and honest holdout."""
import unittest

from nerve_awim.recursive_evolution_v19 import (
    RetrievalGenome, EvalScore, RecursiveEvolutionLoop,
    SyntheticMemoryObjective, demo,
)


class MonotonicFixture:
    def __init__(self):
        self.calls = {"train": 0, "validation": 0, "holdout": 0}

    def evaluate(self, genome, split):
        self.calls[split] += 1
        rate = min(.9, .3 + genome.trigram_weight * .15)
        return EvalScore(rate, round(rate * 20), 20, 0)


class LeakingFixture(MonotonicFixture):
    def evaluate(self, genome, split):
        result = super().evaluate(genome, split)
        if genome.trigram_weight > 0:
            return EvalScore(result.accuracy, result.hits,
                             result.queries, 1)
        return result


class HoldoutFailure(MonotonicFixture):
    def evaluate(self, genome, split):
        result = super().evaluate(genome, split)
        if split == "holdout" and genome.trigram_weight:
            return EvalScore(.1, 2, 20, 0)
        return result


class RecursiveEvolutionV19Tests(unittest.TestCase):
    def test_multiple_generations_change_data_only_recipe(self):
        objective = MonotonicFixture()
        def mutate(parent, rng):
            return RetrievalGenome(parent.token_weight,
                                   min(5, parent.trigram_weight + 1))
        report = RecursiveEvolutionLoop(
            objective=objective, generations=4,
            offspring=2, seed=4, patience=2,
            mutation=mutate
        ).run()
        self.assertGreater(report["selected"]["trigram_weight"], 1)
        self.assertGreater(report["selected_validation"]["accuracy"],
                           report["baseline_validation"]["accuracy"])
        self.assertEqual(report["status"], "candidate_for_human_review")
        # Holdout is not inspected within search; only final comparisons.
        self.assertEqual(objective.calls["holdout"], 2)

    def test_unsafe_candidate_cannot_evolve(self):
        obj = LeakingFixture()
        def mutation(parent, rng):
            return RetrievalGenome(3, 1)
        report = RecursiveEvolutionLoop(
            objective=obj, generations=3, offspring=2,
            mutation=mutation, patience=2
        ).run()
        self.assertEqual(report["status"], "no_verified_improvement")
        self.assertEqual(report["selected"], {
            "token_weight": 3, "trigram_weight": 0
        })
        self.assertTrue(all(not row["accepted"]
                            for generation in report["lineage"]
                            for row in generation.get("evaluated", [])))

    def test_holdout_regression_rejects_promotion(self):
        obj = HoldoutFailure()
        def mutation(parent, rng):
            return RetrievalGenome(parent.token_weight, 1)
        result = RecursiveEvolutionLoop(
            objective=obj, generations=2,
            offspring=2, mutation=mutation
        ).run()
        self.assertGreater(result["selected_validation"]["accuracy"],
                           result["baseline_validation"]["accuracy"])
        self.assertEqual(result["status"], "no_verified_improvement")

    def test_invalid_genomes_and_budgets_rejected(self):
        with self.assertRaises(ValueError):
            RetrievalGenome(token_weight=0, trigram_weight=0)
        with self.assertRaises(ValueError):
            RetrievalGenome(token_weight=3, trigram_weight=6)
        with self.assertRaises(ValueError):
            RecursiveEvolutionLoop(objective=MonotonicFixture(),
                                   generations=13)
        with self.assertRaises(ValueError):
            RecursiveEvolutionLoop(objective=MonotonicFixture(),
                                   offspring=0)
        with self.assertRaises(TypeError):
            RecursiveEvolutionLoop(
                objective=MonotonicFixture(),
                mutation=lambda genome, randomizer: "untrusted text"
            ).run()

    def test_real_scoped_sql_objective_runs_and_is_reproducible(self):
        first = demo(generations=3, seed=19)
        second = demo(generations=3, seed=19)
        for report in (first, second):
            self.assertEqual(report["baseline_validation"]["cross_tenant_leaks"], 0)
            self.assertEqual(report["report_only_holdout"]["cross_tenant_leaks"], 0)
            self.assertLessEqual(report["generations_run"], 3)
            self.assertLessEqual(report["candidates_evaluated"], 18)
            self.assertIn(report["status"], (
                "candidate_for_human_review", "no_verified_improvement"))
        self.assertEqual(first["selected"], second["selected"])
        self.assertEqual(first["lineage"], second["lineage"])

    def test_resumed_recipe_regression_resets_to_canonical(self):
        class DriftedObjective:
            def evaluate(self, genome, split):
                success = .9 if genome.trigram_weight == 0 else .2
                return EvalScore(success, round(success * 10), 10, 0)
        def mutation(parent, rng):
            return RetrievalGenome(parent.token_weight, 1)
        report = RecursiveEvolutionLoop(
            objective=DriftedObjective(), generations=2,
            mutation=mutation
        ).run(
            baseline=RetrievalGenome(3, 3),
            previous_population=(RetrievalGenome(3, 3),)
        )
        self.assertTrue(report['reset_on_validation_drift'])
        self.assertEqual(report['baseline'],
                         {'token_weight': 3, 'trigram_weight': 0})
        self.assertEqual(report['status'], 'no_verified_improvement')
    def test_known_objective_baseline_can_be_evaluated(self):
        objective = SyntheticMemoryObjective()
        try:
            score = objective.evaluate(RetrievalGenome(3, 0), "train")
            self.assertEqual(score.cross_tenant_leaks, 0)
            self.assertGreaterEqual(score.accuracy, 0)
            with self.assertRaises(ValueError):
                objective.evaluate(RetrievalGenome(), "unexpected")
        finally:
            objective.close()


if __name__ == "__main__":
    unittest.main()
