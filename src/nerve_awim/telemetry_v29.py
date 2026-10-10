"""v2.9 bounded structured event telemetry; no patient data or credentials."""
from collections import deque
from dataclasses import dataclass
from time import time

@dataclass(frozen=True)
class Event:
    sequence:int
    category:str
    status:str
    incident:int
    timestamp:float

class EventTrace:
    def __init__(self, capacity=1024):
        if not isinstance(capacity,int) or capacity<1:
            raise ValueError("invalid capacity")
        self.events=deque(maxlen=capacity)
        self.count=0
    def record(self,category,status,incident=0):
        if category not in ("sensor","control","recovery","identity","audit"):
            raise ValueError("unknown event category")
        if status not in ("ok","denied","missing","unavailable","error"):
            raise ValueError("unknown event status")
        if not isinstance(incident,int) or incident<0:
            raise ValueError("invalid incident")
        self.count+=1
        event=Event(self.count,category,status,incident,time())
        self.events.append(event)
        return event
    def summary(self):
        return {"total":self.count,"retained":len(self.events),
                "denied":sum(e.status=="denied" for e in self.events),
                "unavailable":sum(e.status=="unavailable" for e in self.events)}
