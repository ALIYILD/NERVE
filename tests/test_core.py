import unittest
from nerve_awim.core import WorldCore, State, Action, Observation, PolicyGate, run_step

class CoreTests(unittest.TestCase):
    def test_prediction(self):
        self.assertAlmostEqual(WorldCore().predict(State(1.0), Action(1)).value, 1.25)

    def test_quality(self):
        with self.assertRaises(ValueError):
            WorldCore().assimilate(Observation(1.0, 0.2))

    def test_safe_step(self):
        result = run_step(WorldCore(), PolicyGate(), State(0), Action(1), Observation(0.25, 1.0))
        self.assertAlmostEqual(result["absolute_prediction_error"], 0)

if __name__ == "__main__":
    unittest.main()
