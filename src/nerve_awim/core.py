"""Deterministic action-conditioned toy dynamics; not learned AI or clinical advice."""
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class Observation:
    value: float
    quality: float
    source: str = "synthetic"

@dataclass(frozen=True)
class State:
    value: float

@dataclass(frozen=True)
class Action:
    direction: Literal[-1, 0, 1]

class PolicyGate:
    def authorize(self, action: Action) -> bool:
        return action.direction in (-1, 0, 1)

class WorldCore:
    """Toy model x[t+1] = x[t] + 0.25*a[t]; replace with learned dynamics."""
    def predict(self, state: State, action: Action) -> State:
        return State(state.value + 0.25 * action.direction)

    def assimilate(self, observation: Observation) -> State:
        if not 0.0 <= observation.quality <= 1.0 or observation.quality < 0.5:
            raise ValueError("Observation quality below threshold")
        return State(observation.value)

def run_step(model: WorldCore, gate: PolicyGate, state: State, action: Action, next_observation: Observation) -> dict:
    if not gate.authorize(action):
        raise PermissionError("Action not authorised")
    prediction = model.predict(state, action)
    actual = model.assimilate(next_observation)
    return {"predicted": prediction.value, "observed": actual.value,
            "absolute_prediction_error": abs(prediction.value - actual.value)}
