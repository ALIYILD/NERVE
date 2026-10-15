"""v2.5 signed approval verification with incident-specific durable replay ledger.

HMAC is suitable only for a tightly controlled shared-secret simulation.
Production should use an external IdP, KMS-backed signing, authenticated
operator identity, and audited key rotation. Never commit live secrets.
"""
from dataclasses import dataclass
from hashlib import sha256
import hmac,json,sqlite3
from pathlib import Path
from .recovery_v22 import Approval
from .recovery_v24 import EvidenceGatedRecovery

@dataclass(frozen=True)
class SignedApproval:
    principal:str
    role:str
    incident:int
    nonce:str
    expires_at:int
    signature:str

def payload(principal,role,incident,nonce,expires_at):
    return json.dumps(dict(principal=principal,role=role,incident=incident,
        nonce=nonce,expires_at=expires_at),sort_keys=True,separators=(",",":")).encode()

def sign_approval(secret,principal,role,incident,nonce,expires_at):
    signature=hmac.new(secret,payload(principal,role,incident,nonce,expires_at),sha256).hexdigest()
    return SignedApproval(principal,role,incident,nonce,expires_at,signature)

class ApprovalLedger:
    def __init__(self,path):
        self.path=str(Path(path))
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS approvals (nonce TEXT PRIMARY KEY, incident INTEGER NOT NULL, principal TEXT NOT NULL, approved_at INTEGER NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, incident INTEGER, event TEXT NOT NULL, created_at INTEGER NOT NULL)")
    def record(self,approval,now):
        with sqlite3.connect(self.path) as db:
            try:
                db.execute("INSERT INTO approvals VALUES (?,?,?,?)",
                    (approval.nonce,approval.incident,approval.principal,now))
            except sqlite3.IntegrityError:
                return False
        return True
    def event(self,incident,name,now):
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO events(incident,event,created_at) VALUES (?,?,?)",(incident,name,now))
    def records(self):
        with sqlite3.connect(self.path) as db:
            return db.execute("SELECT incident,event,created_at FROM events ORDER BY id").fetchall()

class SignedRecovery(EvidenceGatedRecovery):
    def __init__(self,*,secret,ledger_path,**kwargs):
        if not isinstance(secret,bytes) or len(secret)<16:raise ValueError("minimum 16-byte secret")
        super().__init__(**kwargs)
        self._secret=secret
        self.ledger=ApprovalLedger(ledger_path)
    def authorize(self,approval):
        # Prevent bypass through the legacy unverified approval API.
        return False
    def authorize_signed(self,approval:SignedApproval,now:int):
        if not isinstance(approval,SignedApproval) or not isinstance(now,int):
            return False
        expected=hmac.new(self._secret,payload(approval.principal,approval.role,
            approval.incident,approval.nonce,approval.expires_at),sha256).hexdigest()
        valid=(hmac.compare_digest(expected,approval.signature)
            and approval.expires_at>=now
            and approval.role=="supervisor" and approval.incident==self.incident
            and bool(approval.principal) and bool(approval.nonce)
            and self.recovery_ready()
            and self.verdict is not None and self.verdict.accepted)
        if not valid:
            self.ledger.event(self.incident,"approval_denied",now)
            return False
        if not self.ledger.record(approval,now):
            self.ledger.event(self.incident,"replay_denied",now)
            return False
        # Call v2.2 approval directly, bypassing this class's legacy-blocking override.
        granted=super(EvidenceGatedRecovery,self).authorize(
            Approval(approval.principal,approval.role,approval.incident,approval.nonce))
        self.ledger.event(self.incident,"approval_accepted" if granted else "approval_denied",now)
        return granted
