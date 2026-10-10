"""Observable wrapper for existing simulation runtime. Not real-device control."""
from .runtime_v28 import NerveResearchRuntime
from .telemetry_v29 import EventTrace

class ObservedNerveRuntime:
    def __init__(self,*,trace=None,**kwargs):
        self.runtime=NerveResearchRuntime(**kwargs)
        self.trace=trace if trace is not None else EventTrace()
    def tick(self):
        result=self.runtime.tick()
        self.trace.record("control","ok" if result.action is not None else "unavailable",result.incident)
        return result
    def sensor_missing(self):
        self.runtime.sensor_missing()
        self.trace.record("sensor","missing",self.runtime.controller.incident)
    def observe(self,timestamp,*,position=None,velocity=None):
        result=self.runtime.observe(timestamp,position=position,velocity=velocity)
        self.trace.record("sensor","ok",self.runtime.controller.incident)
        return result
    def authorise_recovery(self,token,approval,now):
        approved=self.runtime.authorise_recovery(token,approval,now)
        self.trace.record("identity","ok" if approved else "denied",
                          self.runtime.controller.incident)
        return approved
