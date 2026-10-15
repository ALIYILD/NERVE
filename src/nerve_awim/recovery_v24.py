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
    def _on_recovery_reset(self):
        self.evidence=[]
        self.verdict=None
    def _on_recovery_observation(self,observation):
        self.evidence.append(dict(observation))
        self.verdict=self.evaluator.evaluate(self.evidence)
        if not self.verdict.accepted:
            self.audit.append(("evidence_rejected",self.incident,self.verdict.reason))
    def recovery_ready(self):
        return (super().recovery_ready() and self.verdict is not None
                and self.verdict.accepted)
    def authorize(self,approval:Approval):
        if self.verdict is None or not self.verdict.accepted:
            self.audit.append(("evidence_gate_denied",self.incident))
            return False
        return super().authorize(approval)
