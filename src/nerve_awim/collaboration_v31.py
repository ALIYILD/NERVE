"""v3.1 typed predictive collaboration with contextual, evidence-scoped memory.

Simple scalar transition models, not LLM agents or physical robotics.
The shared baseline has access to the SAME specialists and inputs, ensuring a
fair comparison of coordination and memory rather than capability coverage.
"""
from dataclasses import dataclass
from math import isfinite
from .agents_v30 import Task,Agent,Coordinator

@dataclass(frozen=True)
class Prediction:
    task_id:str
    next_state:float
    source:str
    agents:tuple[str,...]
    memory_used:bool

class ContextMemory:
    def __init__(self):self.entries={}
    def remember(self,context,observed_gain,source):
        if not context or not source or not isfinite(observed_gain):
            raise ValueError("invalid evidence")
        self.entries.setdefault(context,[]).append((observed_gain,source))
    def retrieve(self,context):
        records=self.entries.get(context,[])
        if not records:return None
        # Only previous observed transitions contribute; never target labels.
        return (sum(r[0] for r in records)/len(records),
                tuple(sorted(set(r[1] for r in records))))

class PredictiveCoordinator:
    def __init__(self,agents,memory=None):
        self.router=Coordinator(agents)
        self.memory=memory if memory is not None else ContextMemory()
    def predict(self,task_id,context,state,action,source):
        if not all(isfinite(v) for v in (state,action)):
            raise ValueError("nonfinite state or action")
        task=Task(task_id,context,action,source)
        agent_output=self.router.dispatch(task)
        base_gain=next(a.gain for a in self.router.agents if a.agent_id==agent_output.agent_id)
        old=self.memory.retrieve(context)
        # Equal-prior smoothing: only previous feedback may affect prediction.
        gain=base_gain if old is None else (base_gain+old[0])/2
        return Prediction(task_id,state+gain*action,source,(agent_output.agent_id,),old is not None)
    def observe(self,context,previous_state,action,observed_next,source):
        if action==0:return
        if not all(isfinite(v) for v in (previous_state,action,observed_next)):
            raise ValueError("nonfinite observation")
        self.memory.remember(context,(observed_next-previous_state)/action,source)

class EqualCapabilityBaseline:
    """One dispatcher with access to every specialist, but no contextual feedback."""
    def __init__(self,agents):self.router=Coordinator(agents)
    def predict(self,task_id,context,state,action,source):
        result=self.router.dispatch(Task(task_id,context,action,source))
        return Prediction(task_id,state+result.value,source,(result.agent_id,),False)
