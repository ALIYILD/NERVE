"""Host-private synthetic episode journal, not an approved-fact memory.

Only a trusted receipt importer should submit scientific_validation_v1 records.
The synthetic marker is a host assertion, not a PHI detector. Hash chains detect
accidental/partial tampering, not a privileged attacker rewriting every checksum.
"""
from dataclasses import asdict
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat

FIELDS=set('episode_id context_hash agent candidate_id policy_version inputs_hash action output evaluator_verdict format_ok evidence_ok real_world_outcome outcome_source timestamps source_sha256 stratum failure_class synthetic_only source_kind'.split())
MAX_RECORDS=10000
MAX_BYTES=64*1024*1024
ZERO='0'*64
TRIGGERS={name:f"CREATE TRIGGER {name} BEFORE {operation} ON episodes BEGIN SELECT RAISE(ABORT, 'append_only'); END"
          for name,operation in [('episodes_no_update','UPDATE'),('episodes_no_delete','DELETE')]}


def _json(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def _hash(value):return sha256(_json(value).encode()).hexdigest()


def _episode(value):
    if type(value) is not dict or set(value)!=FIELDS:raise ValueError('exact_episode_schema_required')
    for key in ('episode_id','agent','candidate_id','policy_version','evaluator_verdict','outcome_source','stratum','failure_class'):
        if type(value[key]) is not str or not re.fullmatch('[A-Za-z0-9_.:/-]{1,200}',value[key]):raise ValueError('bounded_episode_identifier_required')
    for key in ('context_hash','inputs_hash'):
        if type(value[key]) is not str or not re.fullmatch('[0-9a-f]{64}',value[key]):raise ValueError('episode_hash_required')
    for key in ('action','output'):
        if type(value[key]) is not str or not 1<=len(value[key])<=16384:raise ValueError('bounded_episode_text_required')
    if (type(value['format_ok']) is not bool or (value['evidence_ok'] is not None and type(value['evidence_ok']) is not bool)
            or value['synthetic_only'] is not True or value['source_kind']!='scientific_validation_v1'
            or value['real_world_outcome'] is not None):raise ValueError('synthetic_receipt_only')
    pins=value['source_sha256']
    if (type(pins) is not dict or not 1<=len(pins)<=100
            or any(type(k) is not str or not 1<=len(k)<=256 or type(v) is not str or not re.fullmatch('[0-9a-f]{64}',v) for k,v in pins.items())):
        raise ValueError('bounded_source_pins_required')
    times=value['timestamps']
    if times is not None and (type(times) is not dict or not 1<=len(times)<=8):raise ValueError('timestamps_required')
    for key,v in (times or {}).items():
        if type(key) is not str or not 1<=len(key)<=64:raise ValueError('timestamp_key_required')
        if not ((type(v) is str and 1<=len(v)<=100) or (type(v) in (int,float) and math.isfinite(v) and v>=0)):
            raise ValueError('bounded_timestamp_required')
    encoded=_json(value)
    if len(encoded.encode())>65536:raise ValueError('episode_size_limit')
    return encoded


class ExperienceStore:
    def __init__(self,path,gateway,scope,enabled=True):
        if type(enabled) is not bool:raise ValueError('boolean_enabled_required')
        self.path=Path(path).absolute();self.gateway=gateway;self.scope=scope;self.enabled=enabled

    def _off(self):return {'status':'off','reason':'disabled','episodes':[]}
    def _require(self,actor,permission):self.gateway._require(actor,self.scope,permission)

    def _connect(self):
        mode=self.path.lstat()
        if not stat.S_ISREG(mode.st_mode) or stat.S_IMODE(mode.st_mode)!=0o600 or mode.st_size>MAX_BYTES:
            raise ValueError('private_bounded_regular_store_required')
        return sqlite3.connect(self.path.as_uri()+'?mode=rw',uri=True,timeout=10)

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

    def initialize(self,actor):
        if not self.enabled:return self._off()
        self._require(actor,'propose')
        fd=os.open(self.path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
        with self._connect() as db:
            db.execute('CREATE TABLE metadata(id INTEGER PRIMARY KEY CHECK(id=1),scope TEXT,count INTEGER,head TEXT)')
            db.execute('CREATE TABLE episodes(sequence INTEGER PRIMARY KEY,episode_id TEXT UNIQUE,payload TEXT,payload_hash TEXT,previous_hash TEXT,chain_hash TEXT,stratum TEXT,candidate_id TEXT,policy_version TEXT,failure_class TEXT)')
            for sql in TRIGGERS.values():db.execute(sql)
            for field in ('stratum','candidate_id','policy_version','failure_class'):
                db.execute(f'CREATE INDEX episodes_{field} ON episodes({field})')
            db.execute('INSERT INTO metadata VALUES(1,?,0,?)',(_json(asdict(self.scope)),ZERO))
        return {'status':'live','count':0}

    def status(self,actor):
        if not self.enabled:return self._off()
        self._require(actor,'read')
        if not self.path.exists():return {'status':'off','reason':'no_data','episodes':[]}
        try:
            with self._connect() as db:
                db.execute('BEGIN');rows,head=self._validate(db)
        except (sqlite3.Error,OSError,ValueError,KeyError,TypeError):return {'status':'degraded','reason':'integrity_failure','read_only':True}
        self._require(actor,'read')
        return {'status':'live','count':len(rows),'head':head}

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

    def query(self,actor,*,stratum=None,candidate_id=None,policy_version=None,failure_class=None):
        if not self.enabled:return self._off()
        self._require(actor,'read')
        if not self.path.exists():return {'status':'off','reason':'no_data','episodes':[]}
        with self._connect() as db:
            db.execute('BEGIN');rows,head=self._validate(db)
        filters=dict(stratum=stratum,candidate_id=candidate_id,policy_version=policy_version,failure_class=failure_class)
        if any(v is not None and (type(v) is not str or len(v)>200) for v in filters.values()):raise ValueError('bounded_filter_required')
        selected=[row for row in rows if all(v is None or row[k]==v for k,v in filters.items())]
        self._require(actor,'read')
        return {'status':'live','episodes':selected,'count':len(selected),'head':head}

    def export(self,actor,path):
        if not self.enabled:return self._off()
        result=self.query(actor)
        if result['status']!='live':return result
        data=b''.join((_json(e)+'\n').encode() for e in result['episodes'])
        rolling=ZERO
        for line in data.splitlines(keepends=True):rolling=sha256(bytes.fromhex(rolling)+line).hexdigest()
        manifest={'version':'experience-export-v1','count':result['count'],'store_head':result['head'],
                  'sha256':sha256(data).hexdigest(),'rolling_sha256':rolling,'synthetic_only':True}
        path=Path(path);side=Path(str(path)+'.manifest.json');meta=(_json(manifest)+'\n').encode()
        reconciled=False
        writes=((path,data),(side,meta))
        if path.exists() or side.exists() or path.is_symlink() or side.is_symlink():
            if not path.exists():raise ValueError('export_exists_or_incomplete')
            for target in (path,side):
                if target==side and not target.exists() and not target.is_symlink():continue
                mode=target.lstat()
                if not stat.S_ISREG(mode.st_mode) or stat.S_IMODE(mode.st_mode)!=0o600 or mode.st_size>MAX_BYTES:
                    raise ValueError('private_regular_export_required')
            if path.read_bytes()!=data:raise ValueError('export_exists_or_incomplete')
            if side.exists():
                if side.read_bytes()!=meta:raise ValueError('export_exists_or_incomplete')
                self._require(actor,'read')
                return {'status':'live','manifest':manifest,'rewritten':False}
            # Recover only a completed, byte-exact payload publication. Never
            # repair incomplete payload bytes or overwrite any manifest.
            reconciled=True;writes=((side,meta),)
        self._require(actor,'read')
        for target,raw in writes:
            fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
            directory=os.open(target.parent,os.O_RDONLY)
            try:os.fsync(directory)
            finally:os.close(directory)
        return {'status':'live','manifest':manifest,'rewritten':not reconciled,'reconciled':reconciled}
