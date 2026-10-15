"""Scoped trusted-host rejection adjudications, not authenticated efficacy metrics.

No model calls or automatic promotion. Changed bank identities alone never waive
rejections: independent new-bank verification is not implemented. Private local
capabilities do not provide remote authentication or protection from a host that
rewrites all journal hashes and receipts. Novelty uses typed evidence fingerprints,
not a proof of natural-language semantic equivalence. Only a cluster key absent
from ALL failure clusters at rejection time can authorize an evidence exception;
new members or changed hashes within an existing cluster do not suffice.
"""
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
import stat

from . import scientific_candidates as candidates

_json,_hash=candidates._json,candidates._hash
MAX_ROWS=1000
MAX_BYTES=32*1024*1024
ZERO='0'*64
SEMANTIC_FIELDS=('context_hash','inputs_hash','action','output','evaluator_verdict','format_ok','evidence_ok','stratum','failure_class')
RECEIPT_FIELDS={'candidate_sha256','hypothesis_sha256','verdict','evaluator_id','model_digest','task_bank_sha256','reason','study_report','study_report_sha256'}
TRIGGERS={name:f"CREATE TRIGGER {name} BEFORE {op} ON rejections BEGIN SELECT RAISE(ABORT, 'append_only'); END"
          for name,op in [('reject_no_update','UPDATE'),('reject_no_delete','DELETE')]}


def _receipt(proposal,receipt):
    if type(receipt) is not dict or set(receipt)!=RECEIPT_FIELDS:raise ValueError('exact_host_adjudication_required')
    if receipt['verdict']!='evaluated_rejected':raise ValueError('evaluated_rejection_required')
    for field in ('candidate_sha256','hypothesis_sha256','model_digest','task_bank_sha256'):
        if type(receipt[field]) is not str or not re.fullmatch('[0-9a-f]{64}',receipt[field]):raise ValueError('receipt_hash_required')
    if receipt['candidate_sha256']!=proposal['candidate_sha256'] or receipt['hypothesis_sha256']!=proposal['hypothesis_sha256']:
        raise ValueError('receipt_candidate_binding_changed')
    if type(receipt['evaluator_id']) is not str or not re.fullmatch('[A-Za-z0-9_.:-]{1,96}',receipt['evaluator_id']):
        raise ValueError('host_evaluator_required')
    if type(receipt['reason']) is not str or not 1<=len(receipt['reason'])<=1000:raise ValueError('bounded_rejection_reason_required')
    report=receipt['study_report']
    if (type(report) is not dict or set(report)!={'schema','candidate_sha256','hypothesis_sha256','verdict','metrics'}
            or report['schema']!='scientific_rejection_report_v1' or report['verdict']!='evaluated_rejected'
            or report['candidate_sha256']!=proposal['candidate_sha256']
            or report['hypothesis_sha256']!=proposal['hypothesis_sha256']
            or type(report['metrics']) is not dict or not report['metrics']
            or len(_json(report).encode())>16384 or receipt['study_report_sha256']!=_hash(report)):
        raise ValueError('bounded_matching_study_report_required')
    return _hash(receipt)


def _semantic(proposal,episodes):
    cluster=proposal['hypothesis']['cluster']
    by_id={episode['episode_id']:episode for episode in episodes}
    fingerprints=[]
    for member in cluster['members']:
        episode=by_id[member['episode_id']]
        if _hash(episode)!=member['payload_sha256']:raise ValueError('authoritative_episode_changed')
        fingerprints.append(_hash({key:episode[key] for key in SEMANTIC_FIELDS}))
    return {'stratum':cluster['stratum'],'failure_class':cluster['failure_class'],'members':sorted(set(fingerprints))}


def candidate_distance(left,right):
    """Typed-field Hamming distance; does not register new combinations.

    Current distinct registered candidates have distance >=2. The <=1 rule is
    retained for future expanded registries, without claiming such a candidate
    currently passes authoritative hypothesis validation.
    """
    for config in (left,right):
        if (type(config) is not dict or set(config)!=candidates.CONFIG_FIELDS
                or type(config['conflict_detection']) is not bool
                or type(config['retrieval_k']) is not int or config['retrieval_k'] not in (4,8)
                or type(config['prompt_template']) is not str or config['prompt_template'] not in ('evidence_json_v1','json_contract_first_v1')
                or type(config['abstention_threshold']) is not str or config['abstention_threshold'] not in ('strict','strict_with_evidence_check')
                or config['tool_rule']!='evidence_only'):
            raise ValueError('typed_candidate_fields_required')
    return sum(left[key]!=right[key] for key in candidates.CONFIG_FIELDS)



class NegativeEvidenceJournal:
    def __init__(self,path,gateway,scope,experience_store):
        self.path=Path(path).absolute();self.gateway=gateway;self.scope=scope;self.experience_store=experience_store

    def _require(self,actor,write=False):
        self.gateway._require(actor,self.scope,'read')
        if write:self.gateway._require(actor,self.scope,'approve')

    def _connect(self):
        mode=self.path.lstat()
        if not stat.S_ISREG(mode.st_mode) or stat.S_IMODE(mode.st_mode)!=0o600 or mode.st_size>MAX_BYTES:
            raise ValueError('private_bounded_journal_required')
        return sqlite3.connect(self.path.as_uri()+'?mode=rw',uri=True,timeout=10)

    def initialize(self,actor):
        self._require(actor,True)
        fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
        with self._connect() as db:
            db.execute('CREATE TABLE metadata(id INTEGER PRIMARY KEY CHECK(id=1),scope TEXT,count INTEGER,head TEXT)')
            db.execute('CREATE TABLE rejections(sequence INTEGER PRIMARY KEY,receipt_id TEXT UNIQUE,payload TEXT,payload_hash TEXT,previous_hash TEXT,chain_hash TEXT)')
            for sql in TRIGGERS.values():db.execute(sql)
            db.execute('INSERT INTO metadata VALUES(1,?,0,?)',(_json(asdict(self.scope)),ZERO))
        return {'status':'live','count':0}

    def _validate(self,db):
        if db.execute('PRAGMA integrity_check').fetchone()!=('ok',):raise ValueError('journal_integrity_failure')
        meta=db.execute('SELECT scope,count,head FROM metadata WHERE id=1').fetchall()
        if len(meta)!=1 or meta[0][0]!=_json(asdict(self.scope)):raise ValueError('journal_scope_changed')
        for name,sql in TRIGGERS.items():
            if db.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?",(name,)).fetchone()!=(sql,):
                raise ValueError('append_only_guard_changed')
        rows=db.execute('SELECT sequence,receipt_id,payload,payload_hash,previous_hash,chain_hash FROM rejections ORDER BY sequence').fetchall()
        if len(rows)>MAX_ROWS:raise ValueError('rejection_capacity')
        head=ZERO;result=[]
        for expected,(sequence,identifier,payload,digest,previous,chain) in enumerate(rows,1):
            if len(payload.encode())>262144:raise ValueError('bounded_receipt_required')
            try:record=json.loads(payload)
            except RecursionError as error:raise ValueError('corrupt_receipt_json') from error
            if (sequence!=expected or _json(record)!=payload or sha256(payload.encode()).hexdigest()!=digest
                    or previous!=head or chain!=_hash([sequence,previous,digest])
                    or identifier!=_hash(record) or set(record)!={'proposal','receipt','semantic_evidence','proposal_sha256','receipt_sha256','baseline_cluster_keys'}
                    or record['proposal_sha256']!=_hash(record['proposal'])
                    or record['receipt_sha256']!=_receipt(record['proposal'],record['receipt'])):
                raise ValueError('rejection_chain_changed')
            candidates.validate_config(record['proposal']['candidate'])
            keys=record['baseline_cluster_keys']
            if (type(keys) is not list or not keys or keys!=sorted(keys)
                    or any(type(key) is not list or len(key)!=2 or any(type(v) is not str for v in key) for key in keys)
                    or len({tuple(key) for key in keys})!=len(keys)):
                raise ValueError('baseline_cluster_keys_changed')
            semantic=record['semantic_evidence']
            if (set(semantic)!={'stratum','failure_class','members'} or type(semantic['members']) is not list
                    or not semantic['members'] or semantic['members']!=sorted(set(semantic['members']))
                    or any(type(h) is not str or not re.fullmatch('[0-9a-f]{64}',h) for h in semantic['members'])):
                raise ValueError('semantic_evidence_changed')
            head=chain;result.append(dict(receipt_id=identifier,**record))
        if (meta[0][1],meta[0][2])!=(len(rows),head):raise ValueError('rejection_tail_changed')
        return result,head

    def inspect(self,actor):
        self._require(actor)
        if not self.path.exists():return {'status':'off','reason':'no_data','receipts':[]}
        try:
            with self._connect() as db:
                db.execute('BEGIN');rows,head=self._validate(db)
        except (sqlite3.Error,OSError,ValueError,TypeError,KeyError):
            return {'status':'degraded','reason':'integrity_failure','receipts':[]}
        self._require(actor)
        return {'status':'live','receipts':rows,'count':len(rows),'head':head}

    def record_rejection(self,actor,proposal,receipt):
        self._require(actor,True)
        if not self.path.exists():raise ValueError('explicit_rejection_journal_initialization_required')
        receipt_hash=_receipt(proposal,receipt)
        # Exact same persisted adjudication can be replayed without requiring an
        # old proposal's head to match newly appended evidence; nothing is added.
        existing=self.inspect(actor)
        if existing['status']!='live':raise ValueError('rejection_journal_degraded')
        for row in existing['receipts']:
            if row['receipt_sha256']==receipt_hash and _json(row['proposal'])==_json(proposal):
                self._require(actor,True)
                return {'status':'live','added':False,'receipt_id':row['receipt_id']}
        candidates.validate_hypothesis(proposal,self.experience_store,actor)
        current=self.experience_store.query(actor)
        if current['status']!='live' or current['head']!=proposal['store_head']:raise ValueError('experience_changed')
        record=dict(proposal=proposal,receipt=receipt,semantic_evidence=_semantic(proposal,current['episodes']),
                    proposal_sha256=_hash(proposal),receipt_sha256=receipt_hash,
                    baseline_cluster_keys=sorted({(e['stratum'],e['failure_class']) for e in current['episodes'] if e['failure_class']!='none'}))
        payload=_json(record)
        if len(payload.encode())>262144:raise ValueError('bounded_receipt_required')
        identifier=_hash(record)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE');rows,head=self._validate(db)
            if any(row['receipt_id']==identifier for row in rows):
                self._require(actor,True)
                return {'status':'live','added':False,'receipt_id':identifier}
            if len(rows)>=MAX_ROWS:raise ValueError('rejection_capacity')
            sequence=len(rows)+1;digest=sha256(payload.encode()).hexdigest();chain=_hash([sequence,head,digest])
            db.execute('INSERT INTO rejections VALUES(?,?,?,?,?,?)',(sequence,identifier,payload,digest,head,chain))
            db.execute('UPDATE metadata SET count=?,head=? WHERE id=1',(sequence,chain))
            if db.execute('PRAGMA page_count').fetchone()[0]*db.execute('PRAGMA page_size').fetchone()[0]>MAX_BYTES:raise ValueError('journal_size_limit')
            self._require(actor,True)
        return {'status':'live','added':True,'receipt_id':identifier}

    def filter(self,actor,proposals,*,task_bank_sha256=None):
        self._require(actor)
        if type(proposals) is not list or len(proposals)>16:raise ValueError('bounded_proposal_list_required')
        if task_bank_sha256 is not None and (type(task_bank_sha256) is not str or not re.fullmatch('[0-9a-f]{64}',task_bank_sha256)):
            raise ValueError('task_bank_hash_required')
        journal=self.inspect(actor)
        report={'status':journal['status'],'allowed':[],'blocked':[],
                'new_bank_exception_verified':False,'model_calls':0,'promotion_authorized':False}
        if journal['status']!='live':
            report['reason']=journal['reason'];report['blocked']=[{'candidate_sha256':p.get('candidate_sha256'),
                'reasons':['rejection_journal_unavailable'],'matched_receipt_ids':[]} for p in proposals]
            return report
        report['journal_head']=journal['head'];report['rejection_count']=journal['count']
        for proposal in proposals:
            candidates.validate_hypothesis(proposal,self.experience_store,actor)
            current=self.experience_store.query(actor)
            if current['head']!=proposal['store_head']:raise ValueError('experience_changed')
            semantic=_semantic(proposal,current['episodes']);blocking=[]
            for rejected in journal['receipts']:
                if candidate_distance(proposal['candidate'],rejected['proposal']['candidate'])>1:continue
                new=[semantic['stratum'],semantic['failure_class']] not in rejected['baseline_cluster_keys']
                if not new:blocking.append(rejected['receipt_id'])
            if blocking:report['blocked'].append({'candidate_sha256':proposal['candidate_sha256'],
                'reasons':['exact_or_near_rejection_without_new_cluster_evidence'],'matched_receipt_ids':blocking})
            else:report['allowed'].append(proposal)
        self._require(actor)
        return report
