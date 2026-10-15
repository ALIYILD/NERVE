"""Independent ground-truth implementation. No generator/adapter imports."""
from decimal import Decimal
from hashlib import sha256
import json


def _hash(value):return sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def facts(task):
    result=[]
    for record in task['evidence']:
        content=record['content']
        if ' of sample ' in content:
            measurement,rest=content.split(' of sample ',1)
            entity,quantity=rest.split(': ',1);quantity=quantity.rsplit(' (',1)[0];measurement=measurement.lower()
        elif content.startswith('For '):
            entity,rest=content[4:].split(', the ',1);measurement,quantity=rest[:-1].split(' measurement was ',1)
        elif content.startswith('The laboratory recorded '):
            quantity,rest=content[len('The laboratory recorded '):-1].split(' as ',1);measurement,entity=rest.split(' for ',1)
        else:raise ValueError('independent_truth_unknown_sentence')
        amount,unit=quantity.rsplit(' ',1)
        if not Decimal(amount).is_finite():raise ValueError('nonfinite')
        result.append((entity,measurement,amount,unit,record['source_id'],record['current']))
    return result


def validate(task):
    if _hash({k:v for k,v in task.items() if k!='content_sha256'})!=task['content_sha256']:raise ValueError('task_hash')
    if not 6<=len(task['evidence'])<=12:raise ValueError('record_count')
    if len({r['source_id'] for r in task['evidence']})!=len(task['evidence']):raise ValueError('duplicate_source')
    for record in task['evidence']:
        if _hash({k:v for k,v in record.items() if k!='content_sha256'})!=record['content_sha256']:raise ValueError('record_hash')
    query=task['query'];prefix='What is sample ';suffix="'s mass in mg?"
    if not query.startswith(prefix) or not query.endswith(suffix):raise ValueError('query')
    entity=query[len(prefix):-len(suffix)]
    rows=facts(task)
    matching=[r for r in rows if r[0]==entity and r[1]=='mass' and r[3]=='mg' and r[5]]
    answer={'status':'abstain','entity':'','measurement':'','value':'','unit':'','source_id':''}
    if matching and len({Decimal(r[2]) for r in matching})==1:
        chosen=min(matching,key=lambda r:r[4]);answer=dict(status='answer',entity=entity,measurement='mass',value=chosen[2],unit='mg',source_id=chosen[4])
    if answer!=task['expected']:raise ValueError('independent_ground_truth_mismatch')
    decoys=[r for r in rows if r[0]!=entity]
    if not 3<=len(decoys)<=8:raise ValueError('distractor_count')
    if any(len(r[0])!=len(entity) or sum(a!=b for a,b in zip(r[0],entity))!=1 or r[0][0]!=entity[0] for r in decoys):raise ValueError('near_duplicate_hardness')
    if task['stratum']=='stale-vs-current':
        current=[i for i,r in enumerate(rows) if r[0]==entity and r[5]];stale=[i for i,r in enumerate(rows) if r[0]==entity and not r[5]]
        if not current or not stale or min(stale)<max(current):raise ValueError('stale_order')
    return True
