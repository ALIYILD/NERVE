"""Explicit dev-study companion to the pinned format-only ExperienceStoreV2.

Preserves scoped authority, append-only chain, private storage, and limits.
Receipt provenance is an importer assertion, not a signature or replay proof.
Never silently upgrades or relabels existing format-probe journals.
"""
from dataclasses import asdict
from hashlib import sha256
import json
import re
import sqlite3

from . import experience_store as legacy
from .experience_store import ExperienceStore, MAX_RECORDS, MAX_BYTES, ZERO, TRIGGERS, _json, _hash

FIELDS=legacy.FIELDS|{'source_receipt_sha256','source_ordinal','registration_sha256','model_digest','domain','split'}
SOURCE_KIND='synthetic_study_receipt_v1'


def _episode(value):
    if type(value) is not dict or set(value)!=FIELDS:
        raise ValueError('exact_study_episode_schema_required')
    if (value['source_kind']!=SOURCE_KIND or value['split']!='dev'
            or type(value['source_ordinal']) is not int or not 0<=value['source_ordinal']<10000
            or value['domain'] not in ('scientific-A','scientific-B','scientific','perfflux-sandbox','clinicalos-sandbox')):
        raise ValueError('synthetic_dev_study_provenance_required')
    for key in ('source_receipt_sha256','registration_sha256','model_digest'):
        if type(value[key]) is not str or not re.fullmatch('[0-9a-f]{64}',value[key]):
            raise ValueError('full_study_provenance_hash_required')
    shared={key:value[key] for key in legacy.FIELDS}
    shared['source_kind']='scientific_validation_v1'
    legacy._episode(shared)
    encoded=_json(value)
    if len(encoded.encode())>65536:raise ValueError('episode_size_limit')
    return encoded


def build_episode(*, row, source_receipt_sha256, registration_sha256,
                  model_digest, domain, ordinal, agent='model-research'):
    """Map replayed rows; cannot itself verify caller-supplied judgments."""
    if type(row['strict_correct']) is not bool or type(row['format_ok']) is not bool:
        raise ValueError('boolean_replayed_judgments_required')
    episode=dict(episode_id=_hash([source_receipt_sha256,domain,ordinal,row['candidate_id']]),
        context_hash=row['inputs_hash'], inputs_hash=row['inputs_hash'], agent=agent,
        candidate_id=row['candidate_id'],policy_version=registration_sha256,
        action='replayed_synthetic_dev_evaluation',output=row['raw_output'],
        evaluator_verdict='strict_correct' if row['strict_correct'] else 'strict_incorrect',
        format_ok=row['format_ok'],evidence_ok=row['strict_correct'] if row['format_ok'] else None,
        real_world_outcome=None,outcome_source='synthetic_evaluator',timestamps=None,
        source_sha256={'receipt':source_receipt_sha256,'registration':registration_sha256},
        stratum=row['stratum'],failure_class=row['failure_class'],synthetic_only=True,
        source_kind=SOURCE_KIND,source_receipt_sha256=source_receipt_sha256,
        source_ordinal=ordinal,registration_sha256=registration_sha256,
        model_digest=model_digest,domain=domain,split='dev')
    _episode(episode)
    return episode


class ExperienceStudyStoreV2(ExperienceStore):
    """Append-only v2-compatible storage with explicit synthetic dev-study provenance."""
    def _validate(self,db):
        if db.execute('PRAGMA integrity_check').fetchone()!=('ok',):raise ValueError('sqlite_integrity_failure')
        meta=db.execute('SELECT scope,count,head FROM metadata WHERE id=1').fetchall()
        if len(meta)!=1 or meta[0][0]!=_json(asdict(self.scope)):raise ValueError('scope_binding_changed')
        for name,sql in TRIGGERS.items():
            if db.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?",(name,)).fetchone()!=(sql,):
                raise ValueError('append_only_guard_changed')
        records=db.execute('SELECT sequence,episode_id,payload,payload_hash,previous_hash,chain_hash,stratum,candidate_id,policy_version,failure_class FROM episodes ORDER BY sequence').fetchall()
        if len(records)>MAX_RECORDS:raise ValueError('episode_count_limit')
        previous=ZERO;result=[]
        for i,row in enumerate(records,1):
            sequence,identifier,payload,digest,prev,chain,*indexes=row
            try:episode=json.loads(payload)
            except RecursionError as error:raise ValueError('malformed_episode_payload') from error
            if (sequence!=i or _episode(episode)!=payload or episode['episode_id']!=identifier
                    or digest!=sha256(payload.encode()).hexdigest() or prev!=previous
                    or chain!=_hash([sequence,previous,digest])
                    or indexes!=[episode[k] for k in ('stratum','candidate_id','policy_version','failure_class')]):
                raise ValueError('episode_chain_changed')
            previous=chain;result.append(episode)
        if (meta[0][1],meta[0][2])!=(len(records),previous):raise ValueError('episode_tail_changed')
        return result,previous

    def append_many(self,actor,episodes):
        if not self.enabled:return self._off()
        self._require(actor,'propose')
        if not self.path.exists():return {'status':'off','reason':'no_data','episodes':[]}
        if type(episodes) is not list or not 1<=len(episodes)<=MAX_RECORDS:raise ValueError('bounded_batch_required')
        encoded=[_episode(e) for e in episodes]
        try:
            with self._connect() as db:
                db.execute('BEGIN IMMEDIATE');old,head=self._validate(db)
                known={e['episode_id']:_json(e) for e in old};sequence=len(old);added=0
                for episode,payload in zip(episodes,encoded):
                    key=episode['episode_id']
                    if key in known:
                        if known[key]!=payload:raise ValueError('conflicting_episode_id')
                        continue
                    sequence+=1
                    if sequence>MAX_RECORDS:raise ValueError('episode_count_limit')
                    digest=sha256(payload.encode()).hexdigest();chain=_hash([sequence,head,digest])
                    db.execute('INSERT INTO episodes VALUES(?,?,?,?,?,?,?,?,?,?)',(sequence,key,payload,digest,head,chain,
                        *[episode[k] for k in ('stratum','candidate_id','policy_version','failure_class')]))
                    known[key]=payload;head=chain;added+=1
                if added:
                    db.execute('UPDATE metadata SET count=?,head=? WHERE id=1',(sequence,head))
                    if db.execute('PRAGMA page_count').fetchone()[0]*db.execute('PRAGMA page_size').fetchone()[0]>MAX_BYTES:raise ValueError('store_size_limit')
                self._require(actor,'propose')
            return {'status':'live','added':added,'count':sequence,'head':head}
        except sqlite3.Error as error:raise ValueError('experience_store_degraded') from error
