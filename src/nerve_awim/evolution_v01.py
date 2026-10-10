"""NERVE Evolution v0.1: outcome-aware episodic strategy selection.

MemRL-inspired two-stage retrieval, not a copy of the MemRL implementation.
No LLM weight updates, external API, live tools, or automatic code changes.
"""
from dataclasses import dataclass
from math import isfinite
from .learn_v31 import LearningStore

@dataclass(frozen=True)
class Strategy:
    experience_id: str
    outcome: str
    utility: float
    task: str

class EvolutionMemory:
    def __init__(self, path):
        self.store = LearningStore(path)
    def record(self, agent_id, task, strategy, feedback=None):
        identifier = self.store.record(agent_id, task, strategy)
        if feedback is not None:
            self.reward(agent_id, identifier, feedback)
        return identifier
    def reward(self, agent_id, experience_id, score):
        if (isinstance(score, bool) or not isinstance(score, (int,float))
                or not isfinite(score) or not 0 <= score <= 1):
            raise ValueError("reward must be finite and in [0,1]")
        self.store.feedback(agent_id, experience_id, score)
    def select(self, agent_id, context, limit=5, minimum_utility=0.0):
        if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=20:
            raise ValueError("limit must be between 1 and 20")
        if (not isinstance(minimum_utility,(int,float)) or
                isinstance(minimum_utility,bool) or
                not isfinite(minimum_utility) or not 0 <= minimum_utility <= 1):
            raise ValueError("invalid minimum utility")
        # Stage 1: narrow by context using the existing agent-scoped retrieval.
        # Stage 2: only explicitly evaluated experiences are eligible for
        # utility ranking; unrated memories cannot become action instructions.
        candidates=self.store.recall(agent_id,context,limit=20)
        eligible=[Strategy(x.experience_id,x.outcome,x.score,x.task)
                  for x in candidates if x.score is not None
                  and x.score>=minimum_utility]
        return sorted(eligible,key=lambda x:(-x.utility,x.experience_id))[:limit]
