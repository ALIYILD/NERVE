"""Explicit study-v2 adapter; does not rewrite protected format-probe schema."""
from hashlib import sha256
from pathlib import Path
from ..memory_gateway.experience_study_store_v2 import ExperienceStudyStoreV2, build_episode
from ..memory_gateway.gateway import MemoryGateway
from ..memory_gateway.contracts import MemoryScope
from ..memory_v18 import MemoryAuthority, TrustedMemoryLedger
from . import canonical, digest

class StudyMemory:
    def __init__(self,directory,domain):
        self.domain=domain
        authority=MemoryAuthority()
        self.actor=authority.issue('loop-sdk',domain,permissions=('read','propose'))
        gateway=MemoryGateway(TrustedMemoryLedger(directory/'authority.sqlite',authority))
        self.store=ExperienceStudyStoreV2(directory/'experience-study-v2.sqlite',gateway,MemoryScope('loop-sdk',domain,'dev-episodes'))
        if not self.store.path.exists():self.store.initialize(self.actor)

    def prepare(self,episodes):
        registration=digest({'schema':'loop-sdk-recorded-outcomes-v1','domain':self.domain})
        evaluator=sha256((Path(__file__).parent/'domains.py').read_bytes()).hexdigest()
        rows=[build_episode(row={'task_id':e['id'],'stratum':e['cluster'],'candidate_id':'sandbox-incumbent',
            'raw_output':canonical({'correct':e['correct']}),'strict_correct':e['correct'],'format_ok':True,
            'failure_class':'none' if e['correct'] else e['cluster'],'inputs_hash':digest(e)},
            source_receipt_sha256=e['source_receipt_sha256'],registration_sha256=registration,
            model_digest=evaluator,domain=self.domain,ordinal=i) for i,e in enumerate(episodes)]
        for row,e in zip(rows,episodes):
            row['episode_id']=digest([self.domain,e['source_receipt_sha256'],e['id']])
            # Preserve the original source array ordinal; reordered imports fail closed.
        return rows

    def append(self,episodes):
        rows=self.prepare(episodes)
        for offset in range(0,len(rows),1000):self.store.append_many(self.actor,rows[offset:offset+1000])
        return self.store.query(self.actor)
