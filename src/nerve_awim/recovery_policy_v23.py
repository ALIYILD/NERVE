"""v2.3 independent recovery evidence evaluator and append-only local audit.

Research-only: filesystem logs are not tamper-proof, encrypted or remotely
attested. Identity claims are not authenticated. No hardware safety assurance.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

@dataclass(frozen=True)
class EvidenceVerdict:
    accepted:bool
    reason:str

class RecoveryEvidenceEvaluator:
    def __init__(self,max_velocity_delta=.5,max_position_delta=1.,minimum=2):
        if min(max_velocity_delta,max_position_delta)<=0 or minimum<2:
            raise ValueError("invalid limits")
        self.max_v=max_velocity_delta
        self.max_p=max_position_delta
        self.minimum=minimum
    def evaluate(self,observations):
        ordered=sorted(observations,key=lambda x:x["timestamp"])
        if len(ordered)<self.minimum:return EvidenceVerdict(False,"insufficient")
        if len({x["timestamp"] for x in ordered})!=len(ordered):
            return EvidenceVerdict(False,"duplicate_timestamp")
        for a,b in zip(ordered,ordered[1:]):
            if b["timestamp"]<=a["timestamp"]:return EvidenceVerdict(False,"out_of_order")
            if abs(b["velocity"]-a["velocity"])>self.max_v:
                return EvidenceVerdict(False,"contradictory_velocity")
            if abs(b["position"]-a["position"])>self.max_p:
                return EvidenceVerdict(False,"contradictory_position")
        return EvidenceVerdict(True,"consistent")

class JsonlAudit:
    def __init__(self,path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
    def append(self,event,incident,details=None):
        record={"event":str(event),"incident":int(incident),"details":details or {}}
        canonical=json.dumps(record,sort_keys=True,separators=(",",":"))
        record["sha256"]=sha256(canonical.encode()).hexdigest()
        with self.path.open("a",encoding="utf-8") as f:
            f.write(json.dumps(record,sort_keys=True)+"\n")
        return record
    def read(self):
        if not self.path.exists():return []
        records=[]
        for line in self.path.read_text(encoding="utf-8").splitlines():
            record=json.loads(line)
            digest=record.pop("sha256")
            canonical=json.dumps(record,sort_keys=True,separators=(",",":"))
            if sha256(canonical.encode()).hexdigest()!=digest:
                raise ValueError("audit record integrity mismatch")
            record["sha256"]=digest
            records.append(record)
        return records
