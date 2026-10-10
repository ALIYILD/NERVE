import unittest

from nerve_awim.autoresearch_v04 import VALIDATION, REPORT_ONLY, Proposal
from nerve_awim.worldcore_recursion_v19 import WorldCoreResearchEvolution


def stats(*, goal=1.0, abort=0., completion=1.,
          violations=0., prediction=1.):
    return {
        "completion": completion, "abort": abort,
        "violations": violations, "goal_penalized": goal,
        "prediction_penalized": prediction,
    }


class FakeWorldCore:
    def __init__(self, *, holdout_regression=False, invalid=False):
        self.calls = []
        self.holdout_regression = holdout_regression
        self.invalid = invalid

    def __call__(self, proposal, seeds):
        self.calls.append((proposal, seeds))
        if self.invalid:
            return dict(stats(), goal_penalized=float("nan"))
        if seeds == REPORT_ONLY:
            if self.holdout_regression and proposal.max_missing > 5:
                return stats(abort=1., completion=.4, goal=.2)
            return stats()
        if proposal.max_missing > 5:
            return stats(goal=.7)
        return stats()


class WorldCoreRecursiveV19Tests(unittest.TestCase):
    def test_verified_new_recipe_requires_independent_holdout(self):
        eval = FakeWorldCore()
        loop = WorldCoreResearchEvolution(
            generations=3, offspring=2, seed=5, evaluator=eval,
        )
        loop.mutation = lambda parent, rng, name: Proposal(
            name, min(12, parent.max_missing + 1), .25,
        )
        report = loop.run()
        self.assertEqual(report["status"], "candidate_for_human_review")
        self.assertGreater(report["selected_recipe"]["max_missing"], 5)
        self.assertEqual(sum(seeds == REPORT_ONLY for _, seeds in eval.calls), 2)

    def test_absolute_holdout_abort_rejects_improvement(self):
        eval = FakeWorldCore(holdout_regression=True)
        loop = WorldCoreResearchEvolution(
            generations=2, offspring=1, evaluator=eval,
        )
        loop.mutation = lambda parent, rng, name: Proposal(
            name, min(12, parent.max_missing + 1), .25,
        )
        report = loop.run()
        self.assertEqual(report["status"], "no_deployable_improvement")
        self.assertIn("episode_abort_detected", report[
            "holdout_rejection_reasons"])

    def test_unsafe_validation_never_selected(self):
        def evaluator(proposal, seeds):
            if seeds == VALIDATION and proposal.max_missing > 5:
                return stats(goal=.01, completion=.5, abort=1., violations=1.)
            return stats()
        loop = WorldCoreResearchEvolution(
            generations=2, offspring=2, evaluator=evaluator,
        )
        loop.mutation = lambda parent, rng, name: Proposal(
            name, 6, .25,
        )
        result = loop.run()
        self.assertEqual(result["status"], "no_deployable_improvement")
        self.assertEqual(result["selected_recipe"]["max_missing"], 5)
        self.assertFalse(result["lineage"][0]["candidates"][0][
            "absolute_eligible"])

    def test_malformed_metrics_and_untyped_mutation_are_rejected(self):
        with self.assertRaises(ValueError):
            WorldCoreResearchEvolution(
                evaluator=FakeWorldCore(invalid=True)
            ).run()
        loop = WorldCoreResearchEvolution(
            evaluator=FakeWorldCore())
        loop.mutation = lambda parent, rng, name: {"payload": "untrusted"}
        with self.assertRaises(TypeError):
            loop.run()

    def test_bounded_budget(self):
        with self.assertRaises(ValueError):
            WorldCoreResearchEvolution(generations=20)
        with self.assertRaises(ValueError):
            WorldCoreResearchEvolution(offspring=0)
        out = WorldCoreResearchEvolution(
            generations=1, offspring=2, seed=5,
            evaluator=FakeWorldCore()).run()
        self.assertLessEqual(out["candidate_count"], 2)

    def test_default_frozen_worldcore_evaluator_runs(self):
        report = WorldCoreResearchEvolution(
            generations=1, offspring=2, seed=5
        ).run()
        self.assertIn(report["status"], (
            "candidate_for_human_review", "no_deployable_improvement"))
        self.assertEqual(report["study_protocol"],
                         "nerve-worldcore-recursive-v19")
        self.assertFalse(report["scope"].startswith("Production"))


if __name__ == "__main__":
    unittest.main()
