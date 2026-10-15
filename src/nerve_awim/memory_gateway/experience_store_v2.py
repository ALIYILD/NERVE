"""Versioned synthetic format-probe episodes, never clinical outcomes.

Inherited host-private storage, permissions, export and lifecycle behavior remain
unchanged. The v2 payload is distinct: a verified importer supplies its receipt
hash and source ordinal. These fields are provenance assertions, not signatures.
"""
from dataclasses import asdict
from hashlib import sha256
import json
import re
import sqlite3

from . import experience_store as legacy
from .experience_store import ExperienceStore, MAX_RECORDS, MAX_BYTES, ZERO, TRIGGERS, _json, _hash

FIELDS=legacy.FIELDS|{'schema_ok','source_receipt_sha256','source_ordinal'}
SOURCE_KIND='scientific_format_probe_v1'


def _episode(value):
    if type(value) is not dict or set(value)!=FIELDS:
        raise ValueError('exact_v2_episode_schema_required')
    if (value['source_kind']!=SOURCE_KIND or type(value['schema_ok']) is not bool
            or type(value['source_ordinal']) is not int or not 0<=value['source_ordinal']<=3
            or type(value['source_receipt_sha256']) is not str
            or not re.fullmatch('[0-9a-f]{64}',value['source_receipt_sha256'])):
        raise ValueError('synthetic_format_probe_provenance_required')
    # Reuse the old pure shared-field validator on a temporary copy only.
    # Persist and hash the original v2 source kind and additional fields.
    shared={key:value[key] for key in legacy.FIELDS}
    shared['source_kind']='scientific_validation_v1'
    legacy._episode(shared)
    encoded=_json(value)
    if len(encoded.encode())>65536:raise ValueError('episode_size_limit')
    return encoded


class ExperienceStoreV2(ExperienceStore):
    """Append-only store for the four ordinal positions of format-probe receipts."""
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
        if type(episodes) is not list or not 1<=len(episodes)<=1000:raise ValueError('bounded_batch_required')
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
