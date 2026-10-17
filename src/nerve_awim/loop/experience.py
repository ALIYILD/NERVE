"""Explicit study-v2 adapter; does not rewrite protected format-probe schema."""
from hashlib import sha256
import json
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
            'raw_output':canonical(e),'strict_correct':e['correct'],'format_ok':True,
            'failure_class':'none' if e['correct'] else e['cluster'],'inputs_hash':digest(e)},
            source_receipt_sha256=e['source_receipt_sha256'],registration_sha256=registration,
            model_digest=evaluator,domain=self.domain,ordinal=e.get('source_ordinal',0)) for i,e in enumerate(episodes)]
        for row,e in zip(rows,episodes):
            row['episode_id']=digest([self.domain,e['id']])
            # Identity and explicit source position never depend on batch ordering.
        return rows

    def append(self,episodes):
        rows=self.prepare(episodes)
        self.store.append_many(self.actor,rows)  # One transaction for the entire batch.
        return self.store.query(self.actor)

    def episodes(self):
        return sorted((json.loads(row['output']) for row in self.store.query(self.actor)['episodes']),key=lambda e:e['id'])
