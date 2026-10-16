"""Bounded Loop39-style dev-failure-driven bank mutation; candidate unchanged.

Only the two agreement strata change. No model, label from holdout, or inference.
Reuses Loop39 clustering, with a separately named bank (not candidate) mutation.
"""
from hashlib import sha256
from decimal import Decimal
import hmac
from . import scientific_task_bank_v3 as old
from .scientific_candidates import _clusters
STRATA=old.STRATA
AGREEMENT=('multi-source-agreement','format-variant-agreement')
VERSION='task-bank-v5-hard-agreement-v1'
def propose(episodes,*,research_enabled=True):
 if type(research_enabled) is not bool:raise ValueError('boolean_mode')
 clusters=_clusters(episodes);relevant=[c for c in clusters if c['stratum'] in AGREEMENT and c['failure_class']=='wrong_provenance']
 if not relevant:return {'status':'no_proposals','reason':'no_agreement_provenance_failures','proposals':[],'model_calls':0}
 config={'matching_sources':[6,8,9],'decoys':3,'maximum_records':12,'decimal_places':6,'decoy_value_gap':'0.000001','format_zero_padding':[0,1,2,3,4,5,6],'source_order':'seed-shuffled; smallest source moved last among matching sources','grammar':'same three family-B sentence templates','other_strata':'unchanged generator'}
 body={'mutation':'hard_agreement_bank_v1','config':config,'clusters':[{'stratum':c['stratum'],'failure_class':c['failure_class'],'count':len(c['members']),'cluster_sha256':c['cluster_sha256']} for c in relevant],'predicted_effect':'More provenance choices and lexical/numeric distractions may increase v4 wrong-source errors; not measured until dev study.','risk':'Synthetic difficulty may fail to increase discordance or increase errors in both arms; true conflicts must not be introduced in agreement strata.'}
 return {'status':'proposed','mode':'deterministic_failure_rules' if research_enabled else 'enumeration_fallback','proposals':[dict(body,hypothesis_sha256=old.digest(body))],'model_research_agent':False,'model_calls':0}
def item(seed,split,stratum,index):
 if stratum not in AGREEMENT:return old.item(seed,split,stratum,index)
 identity=hmac.new(seed,f'{VERSION}:{split}:{stratum}:{index}'.encode(),'sha256').hexdigest();entity='N'+identity[:16]
 number=10_000_000+int(identity[16:28],16)%8_900_000_000;value=f'{number//1000000}.{number%1000000:06d}'
 n=(6,8,9)[int(identity[28:30],16)%3];specs=[]
 for j in range(n+3):
  source='src-'+hmac.new(seed,f'{identity}:source:{j}'.encode(),'sha256').hexdigest()[:16]
  if j<n:
   amount=value
   if stratum=='format-variant-agreement':amount=('0'*(j%3))+value+('0'*(j%7))
   name=entity
  else:
   pos=1+(j%15);name=entity[:pos]+('a' if entity[pos]!='a' else 'b')+entity[pos+1:]
   amount=format(Decimal(value)+Decimal(j-n+1)*Decimal('0.000001'),'f')
  specs.append(dict(entity=name,measurement='mass',value=amount,unit='mg',source_id=source,current=True))
 specs.sort(key=lambda r:sha256((identity+r['source_id']).encode()).hexdigest())
 chosen=min((r for r in specs if r['entity']==entity),key=lambda r:r['source_id']);specs.remove(chosen);specs.append(chosen)
 evidence=[]
 for j,s in enumerate(specs):
  pattern=int(sha256((s['source_id']+identity).encode()).hexdigest()[:2],16)%3
  content=(old.TEMPLATES[0].format('Mass',s['entity'],s['value'],'mg','current') if pattern==0 else old.TEMPLATES[1].format(s['entity'],'mass',s['value'],'mg') if pattern==1 else old.TEMPLATES[2].format(s['value'],'mg','mass',s['entity']))
  r={'content':content,'source_id':s['source_id'],'version':2,'current':True,'timestamp':'2026-10-15T12:00:00Z'};r['content_sha256']=old.digest(r);evidence.append(r)
 expected=dict(status='answer',entity=entity,measurement='mass',value=chosen['value'],unit='mg',source_id=chosen['source_id'])
 task={'task_id':split+'-'+identity,'split':split,'stratum':stratum,'query':f"What is sample {entity}'s mass in mg?",'evidence':evidence,'expected':expected,'expected_behavior':'answer'};task['content_sha256']=old.digest(task);return task
