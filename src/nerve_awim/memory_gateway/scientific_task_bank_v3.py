"""New template-family synthetic generator. CPU only; no candidate or model calls."""
from decimal import Decimal
from hashlib import sha256
import hmac
import json

VERSION='task-bank-v3-family-b'
STRATA=('supported-measurement','measurement-decoy','entity-decoy','unit-mismatch','conflict','multi-source-agreement','stale-vs-current','format-variant-agreement','dissenter')
TEMPLATES=('{} of sample {}: {} {} ({}).','For {}, the {} measurement was {} {}.','The laboratory recorded {} {} as {} for {}.')


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(value):return sha256(canonical(value).encode()).hexdigest()


def item(seed,split,stratum,index):
    identity=hmac.new(seed,f'{VERSION}:{split}:{stratum}:{index}'.encode(),'sha256').hexdigest()
    entity='N'+identity[:16];number=100+int(identity[20:28],16)%90000
    value=f'{number//10}.{number%10}';other=f'{(number+7)//10}.{(number+7)%10}'
    specs=[]
    def add(name=entity,measurement='mass',amount=value,unit='mg',current=True):
        tag=hmac.new(seed,f'{identity}:record:{len(specs)}'.encode(),'sha256').hexdigest()
        specs.append({'entity':name,'measurement':measurement,'value':amount,'unit':unit,'current':current,'source_id':'src-'+tag[:16]})
    add(unit='g' if stratum=='unit-mismatch' else 'mg')
    if stratum=='conflict':add(amount=other)
    elif stratum=='multi-source-agreement':add();add();add()
    elif stratum=='stale-vs-current':add(amount=other,current=False)
    elif stratum=='format-variant-agreement':add(amount=value+'0');add(amount='0'+value);add()
    elif stratum=='dissenter':add();add(amount=other)
    elif stratum=='measurement-decoy':add(measurement='dry mass',amount=other);add(measurement='mass fraction',amount=value)
    elif stratum=='entity-decoy':
        near=entity[:8]+('a' if entity[8]!='a' else 'b')+entity[9:];add(name=near,amount=other)
    count=max(6,min(12,len(specs)+3+int(identity[28:30],16)%6,sum(s['entity']==entity for s in specs)+8))
    while len(specs)<count:
        j=len(specs);position=1+(j%15);replacement='a' if entity[position]!='a' else 'b'
        name=entity[:position]+replacement+entity[position+1:]
        add(name=name,measurement=('mass','dry mass','mass fraction')[j%3],amount=value if j%2 else other)
    specs.sort(key=lambda s:sha256((identity+s['source_id']).encode()).hexdigest())
    if stratum=='stale-vs-current':
        stale=next(i for i,s in enumerate(specs) if not s['current']);current=next(i for i,s in enumerate(specs) if s['entity']==entity and s['current'])
        if stale<current:specs[stale],specs[current]=specs[current],specs[stale]
    evidence=[]
    for spec in specs:
        pattern=int(sha256(spec['source_id'].encode()).hexdigest()[:2],16)%3
        n,m,v,u=spec['entity'],spec['measurement'],spec['value'],spec['unit']
        if pattern==0:content=TEMPLATES[0].format(m.capitalize(),n,v,u,'current' if spec['current'] else 'superseded')
        elif pattern==1:content=TEMPLATES[1].format(n,m,v,u)
        else:content=TEMPLATES[2].format(v,u,m,n)
        record={'content':content,'source_id':spec['source_id'],'version':2 if spec['current'] else 1,'current':spec['current'],
                'timestamp':'2026-10-15T12:00:00Z' if spec['current'] else '2026-10-14T12:00:00Z'}
        record['content_sha256']=digest(record);evidence.append(record)
    abstain=stratum in ('unit-mismatch','conflict','dissenter')
    expected={'status':'abstain','entity':'','measurement':'','value':'','unit':'','source_id':''}
    if not abstain:
        support=[s for s in specs if s['entity']==entity and s['measurement']=='mass' and s['unit']=='mg' and s['current'] and Decimal(s['value'])==Decimal(value)]
        source=min(support,key=lambda s:s['source_id']);expected=dict(status='answer',entity=entity,measurement='mass',value=source['value'],unit='mg',source_id=source['source_id'])
    result={'task_id':split+'-'+identity,'split':split,'stratum':stratum,'query':f"What is sample {entity}'s mass in mg?",'evidence':evidence,'expected':expected,'expected_behavior':expected['status']}
    result['content_sha256']=digest(result);return result
