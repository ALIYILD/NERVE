"""Deterministic detection; optional model proposals never establish truth."""
def detect(ledger,actor,task_id):return ledger.detect(actor,task_id)
def suggest(ledger,actor,task_id,claim_ids,*,kind='source_disagreement'):
    return ledger.register_conflict(actor,task_id,claim_ids,kind=kind,suspected=True)
