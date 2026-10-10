"""NERVE v3.0: typed, deterministic specialist-agent orchestration prototype.

No LLM or Hermes is connected. Every result carries explicit provenance.
"""
from dataclasses import dataclass
from math import isfinite

@dataclass(frozen=True)
class Task:
    task_id:str
    capability:str
    value:float
    source:str
    def __post_init__(self):
        if not self.task_id or not self.capability or not self.source or not isfinite(self.value):
            raise ValueError("invalid task")

@dataclass(frozen=True)
class Result:
    task_id:str
    agent_id:str
    value:float
    source:str
    capability:str

@dataclass(frozen=True)
class Agent:
    agent_id:str
    capability:str
    gain:float
    def execute(self,task):
        if self.capability!=task.capability:raise ValueError("unsupported capability")
        return Result(task.task_id,self.agent_id,task.value*self.gain,task.source,task.capability)

class ProvenanceMemory:
    def __init__(self):self.records={}
    def store(self,result):
        if result.task_id in self.records:raise ValueError("duplicate task")
        self.records[result.task_id]=result
    def retrieve(self,task_id):return self.records.get(task_id)

class Coordinator:
    def __init__(self,agents,memory=None):
        self.agents=tuple(agents)
        if len({a.agent_id for a in self.agents})!=len(self.agents):
            raise ValueError("duplicate agent identity")
        self.memory=memory or ProvenanceMemory()
    def dispatch(self,task):
        matching=[a for a in self.agents if a.capability==task.capability]
        if not matching:raise LookupError("no authorised specialist")
        # Deterministic capability routing, not learned delegation.
        agent=min(matching,key=lambda a:a.agent_id)
        output=agent.execute(task)
        self.memory.store(output)
        return output
