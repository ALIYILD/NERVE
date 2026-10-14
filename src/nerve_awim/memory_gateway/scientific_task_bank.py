"""CPU synthetic bank. API roles do not seal files against their trusted host.

The host must isolate the protected directory from generator processes and keep
its seed private. This module does not constitute an independent sealed holdout
service. Splits share semantic families and generation templates; only instances
are disjoint. This is not an unseen-template holdout. No model calls, clinical
records, inference or automatic promotion.
"""
from collections import Counter
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
import re
import stat

from .scientific_structured_tasks import SCHEMA, parse
from ..memory_v18 import MemoryAuthority

VERSION='task-bank-v1'
STRATA=('supported-measurement','measurement-decoy','entity-decoy','unit-mismatch',
        'conflict','multi-source-agreement','stale-vs-current')
RULES=('Use only supplied evidence. Match the exact entity, measurement and unit; do not convert units. '
       'Use records explicitly marked current=true; ignore current=false superseded records. '
       'If no current matching record exists or current matching values conflict, abstain. '
       'If current matching records agree, answer using the lexicographically smallest supporting source_id. '
       'Return exactly the six string fields status, entity, measurement, value, unit, source_id. '
       'An answer has status="answer"; entity is the bare sample identifier. '
       'An abstention has status="abstain" and all other fields empty. No extra keys or prose.')
ROOT=Path(__file__).resolve().parents[3]


def _json(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def _hash(value):return sha256(_json(value).encode()).hexdigest()


def sources():
    paths=('src/nerve_awim/memory_gateway/scientific_task_bank.py',
           'src/nerve_awim/memory_gateway/scientific_structured_tasks.py',
           'src/nerve_awim/memory_v18.py','scripts/build_scientific_task_bank.py')
    return {p:sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}


def _item(seed,split,stratum,index):
    identity=hmac.new(seed,f'{VERSION}:{split}:{stratum}:{index}'.encode(),'sha256').hexdigest()
    entity='N'+identity[:16]
    # Integer arithmetic, exact one-decimal strings, no binary floating-point facts.
    cents=100+int(identity[24:32],16)%90000
    value=f'{cents//10}.{cents%10}'
    alternate=f'{(cents+7)//10}.{(cents+7)%10}'
    base=split+'-'+identity
    def fact(suffix,name=entity,measurement='mass',amount=value,unit='mg',current=True,version=1):
        return dict(content=f'Sample {name} has {measurement} {amount} {unit}.',source_id='src-'+identity[:16]+'-'+suffix,
                    version=version,current=current,timestamp='2026-01-02T00:00:00Z' if current else '2026-01-01T00:00:00Z')
    evidence=[fact('a')]
    if stratum=='measurement-decoy':evidence.append(fact('b',measurement='temperature',amount=alternate,unit='C'))
    elif stratum=='entity-decoy':evidence.insert(0,fact('b',name='D'+identity[:16],amount=alternate))
    elif stratum=='unit-mismatch':evidence=[fact('a',unit='g')]
    elif stratum=='conflict':evidence.append(fact('b',amount=alternate))
    elif stratum=='multi-source-agreement':evidence.append(fact('b'))
    elif stratum=='stale-vs-current':evidence=[fact('a',amount=alternate,current=False),fact('b',version=2)]
    for record in evidence:record['content_sha256']=_hash(record)
    abstain=stratum in ('unit-mismatch','conflict')
    expected=dict(zip(('status','entity','measurement','value','unit','source_id'),
        ('abstain','','','','','') if abstain else ('answer',entity,'mass',value,'mg',
        min(r['source_id'] for r in evidence if r['current'] and value+' mg.' in r['content'] and entity in r['content']))))
    parse(_json(expected))
    result=dict(task_id=base,split=split,stratum=stratum,query=f'What is sample {entity}\'s mass in mg?',
                evidence=evidence,expected=expected,expected_behavior=expected['status'])
    result['content_sha256']=_hash(result)
    return result


def _exclusive_write(path,value):
    data=(_json(value)+'\n').encode()
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as stream:
        stream.write(data);stream.flush();os.fsync(stream.fileno())
    return sha256(data).hexdigest()


def build(directory,*,host_seed):
    """Trusted host only; seed must not be provided to candidate generators."""
    if type(host_seed) is not str or not re.fullmatch('[0-9a-f]{64}',host_seed):
        raise ValueError('explicit_private_256_bit_host_seed_required')
    seed=bytes.fromhex(host_seed);root=Path(directory).resolve()
    root.mkdir(mode=0o700,parents=False,exist_ok=False)
    pins=sources();files={};counts={}
    for split in ('dev','holdout'):
        items=[_item(seed,split,stratum,i) for position,stratum in enumerate(STRATA)
               for i in range(100 if split=='dev' else 43 if position<6 else 42)]
        files[split]=_exclusive_write(root/(split+'.json'),items)
        counts[split]=dict(Counter(item['stratum'] for item in items))
    manifest=dict(version=VERSION,seed_identity=sha256(seed).hexdigest(),rules=RULES,schema=SCHEMA,
                  source_sha256=pins,files=files,counts=counts,total=1000,split_counts={'dev':700,'holdout':300})
    digest=_exclusive_write(root/'manifest.json',manifest)
    fd=os.open(root,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
    if sources()!=pins:raise ValueError('source_changed_during_build')
    return dict(status='live',version=VERSION,manifest_sha256=digest,counts=manifest['split_counts'],
                paths={key:str(root/(key+'.json')) for key in ('dev','holdout','manifest')},
                boundary='Private host files; API guard is not a filesystem sandbox.')


def _read(path,limit):
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    with os.fdopen(fd,'rb') as stream:
        mode=os.fstat(stream.fileno())
        if not stat.S_ISREG(mode.st_mode) or stat.S_IMODE(mode.st_mode)!=0o600:
            raise ValueError('private_regular_file_required')
        raw=stream.read(limit+1)
    if len(raw)>limit:raise ValueError('bounded_bank_required')
    return raw


class ScientificTaskBank:
    def __init__(self,directory,authority,*,expected_manifest_hash,tenant_id,generator_agent_id,
                 gate_actor=None,enabled=True):
        if type(enabled) is not bool or type(authority) is not MemoryAuthority:
            raise ValueError('host_configuration_required')
        if type(expected_manifest_hash) is not str or not re.fullmatch('[0-9a-f]{64}',expected_manifest_hash):
            raise ValueError('external_manifest_pin_required')
        if gate_actor is not None:
            authority.require(gate_actor,'read');authority.require(gate_actor,'approve')
            if gate_actor.tenant_id!=tenant_id or gate_actor.agent_id==generator_agent_id or 'propose' in gate_actor.permissions:
                raise PermissionError('independent_selection_gate_required')
        self.root=Path(directory).resolve();self.authority=authority;self.pin=expected_manifest_hash
        self.tenant_id=tenant_id;self.generator_agent_id=generator_agent_id;self.gate_actor=gate_actor;self.enabled=enabled

    def _verify(self,only_split=None):
        if stat.S_IMODE(self.root.stat().st_mode)!=0o700:raise ValueError('private_directory_required')
        raw=_read(self.root/'manifest.json',100000)
        if sha256(raw).hexdigest()!=self.pin:raise ValueError('manifest_changed')
        manifest=json.loads(raw)
        if (manifest['version']!=VERSION or manifest['rules']!=RULES or _json(manifest['schema'])!=_json(SCHEMA)
                or manifest['source_sha256']!=sources() or manifest['total']!=1000
                or manifest['split_counts']!={'dev':700,'holdout':300}):raise ValueError('bank_protocol_changed')
        items={};ids=set();facts=set()
        for split in ((only_split,) if only_split is not None else ('dev','holdout')):
            data=_read(self.root/(split+'.json'),8000000)
            if sha256(data).hexdigest()!=manifest['files'][split]:raise ValueError('bank_content_changed')
            rows=json.loads(data);counter=Counter()
            if type(rows) is not list or len(rows)!=manifest['split_counts'][split]:raise ValueError('bank_count_changed')
            for row in rows:
                digest=row['content_sha256'];body={k:v for k,v in row.items() if k!='content_sha256'}
                if digest!=_hash(body) or row['split']!=split or row['task_id'] in ids:raise ValueError('invalid_task_identity')
                ids.add(row['task_id']);counter[row['stratum']]+=1;parse(_json(row['expected']))
                for record in row['evidence']:
                    if record['content_sha256']!=_hash({k:v for k,v in record.items() if k!='content_sha256'}):raise ValueError('invalid_provenance_hash')
                    identity=(record['content'],record['source_id'])
                    if identity in facts:raise ValueError('reused_base_fact')
                    facts.add(identity)
            expected={stratum:100 if split=='dev' else 43 if i<6 else 42 for i,stratum in enumerate(STRATA)}
            if dict(counter)!=expected or manifest['counts'][split]!=expected:raise ValueError('stratum_counts_changed')
            items[split]=rows
        return items

    def status(self):
        if not self.enabled:return {'status':'off','reason':'disabled','data_available':False}
        if not (self.root/'manifest.json').exists():return {'status':'off','reason':'no_data','data_available':False}
        try:self._verify()
        except (OSError,ValueError,TypeError,KeyError):return {'status':'degraded','reason':'integrity_failure','data_available':False}
        return {'status':'live','reason':'verified','data_available':True,'manifest_sha256':self.pin}

    def _data(self,split):
        if not self.enabled:raise ValueError('task_bank_off_disabled')
        if not (self.root/'manifest.json').exists():raise ValueError('task_bank_off_no_data')
        try:return self._verify(split)[split]
        except (OSError,ValueError,TypeError,KeyError):
            raise ValueError('task_bank_degraded_integrity_failure') from None

    def development(self,actor):
        self.authority.require(actor,'read')
        if actor.tenant_id!=self.tenant_id or actor.agent_id!=self.generator_agent_id:
            raise PermissionError('generator_role_required')
        return self._data('dev')

    def holdout(self,actor):
        self.authority.require(actor,'read');self.authority.require(actor,'approve')
        if actor is not self.gate_actor or actor.tenant_id!=self.tenant_id:
            raise PermissionError('bound_selection_gate_required')
        return self._data('holdout')
