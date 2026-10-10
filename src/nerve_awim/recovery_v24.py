"""v2.4 integrated evidence-gated simulated recovery.

Fresh, consistent position/velocity observations AND incident-scoped approval
are mandatory. Roles are asserted, not authenticated. Research only.
"""
from .recovery_v22 import AuditedRecovery, Approval
from .recovery_policy_v23 import RecoveryEvidenceEvaluator

class EvidenceGatedRecovery(AuditedRecovery):
    def __init__(self, *, evidence_minimum=2, **kwargs):
        super().__init__(**kwargs)
        self.evaluator=RecoveryEvidenceEvaluator(minimum=evidence_minimum)
        self.evidence=[]
        self.verdict=None
    def miss(self):
        previous=self.incident
        super().miss()
        if self.incident!=previous:
            self.evidence=[]
            self.verdict=None
    def ingest(self,timestamp,*,position=None,velocity=None):
        accepted=super().ingest(timestamp,position=position,velocity=velocity)
        if not accepted:return False
        if self.phase!="active":
            if position is None or velocity is None:
                self.audit.append(("incomplete_evidence",self.incident))
                return True
            self.evidence.append({"timestamp":timestamp,"position":position,"velocity":velocity})
            self.verdict=self.evaluator.evaluate(self.evidence)
            if not self.verdict.accepted:
                self.audit.append(("evidence_rejected",self.incident,self.verdict.reason))
        return True
    def authorize(self,approval:Approval):
        if self.verdict is None or not self.verdict.accepted:
            self.audit.append(("evidence_gate_denied",self.incident))
            return False
        return super().authorize(approval)
