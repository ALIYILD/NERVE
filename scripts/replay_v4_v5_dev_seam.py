"""Doc106 dev outputs only. V5 does not consume raw model output; report that fact."""
import sys,json,socket
from pathlib import Path
from hashlib import sha256
from collections import defaultdict
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from nerve_awim.memory_gateway import scientific_family_b_v4 as v4,scientific_family_b_v5 as v5,scientific_family_b_adapter as adapter
import run_scientific_family_b_v4_sweden as historical
BASE=Path('/Users/aliyildirim/nerve-research-runs/sweden-20261016/final-extracted/v4-dev')
OUT=ROOT/'docs/galahad/evidence/gate-v3_1-dev-seam-replay.json'
def h(p):return sha256(p.read_bytes()).hexdigest()
def run():
 reg=json.loads((BASE/'registration.json').read_text());assert h(BASE/'private-input.json')==reg['input_sha256']
 for name in ['src/nerve_awim/memory_gateway/scientific_family_b_v4.py','src/nerve_awim/memory_gateway/scientific_family_b_adapter.py']:assert h(ROOT/name)==reg['sources'][name]
 tasks=json.loads((BASE/'private-input.json').read_text());lookup={t['task_id']:t for t in tasks}
 schedule=historical.schedule(tasks,reg['arms'],reg['candidate_module'],'dev');assert sha256(historical.canonical(schedule).encode()).hexdigest()==reg['schedule_sha256']
 report=json.loads((BASE/'private-report.json').read_text());rows=report['rows'];assert [(r['task_id'],r['arm']) for r in rows]==[(e['task_id'],e['arm']) for e in schedule]
 table=defaultdict(lambda:dict(n=0,byte_identical=0,numeric_semantically_equal=0,v4_decode_errors=0,v4_correct=0,v5_correct=0,changed_fields={}))
 private=[]
 for row in rows:
  if row['arm']!='candidate':continue
  t=lookup[row['task_id']];p=v4.prepare(t['query'],t['evidence']);a=adapter.decode(row['raw_output'],p);b=v5.decide(t['query'],t['evidence'])
  s=table[t['stratum']];s['n']+=1;s['byte_identical']+=historical.canonical(a)==historical.canonical(b)
  from decimal import Decimal
  semantic=all(a[k]==b[k] for k in a if k!='value') and (a['value']==b['value'] or (a['status']=='answer' and Decimal(a['value'])==Decimal(b['value'])))
  s['numeric_semantically_equal']+=semantic;s['v4_correct']+=row['score']['strict_correct']
  e=t['expected'];correct=b['status']==e['status']
  if correct and b['status']=='answer':correct=all(b[k]==e[k] for k in ('entity','measurement','unit','source_id')) and Decimal(b['value'])==Decimal(e['value'])
  s['v5_correct']+=bool(correct)
  for k in a:
   if a[k]!=b[k]:s['changed_fields'][k]=s['changed_fields'].get(k,0)+1
  private.append({'task_id':t['task_id'],'stratum':t['stratum'],'v4':a,'v5':b,'raw_sha256':sha256(row['raw_output'].encode()).hexdigest()})
 privatepath=Path('/Users/aliyildirim/nerve-research-runs/gate-v3_1-dev-replay');privatepath.mkdir(mode=0o700)
 raw=(json.dumps(private,sort_keys=True,indent=2)+'\n').encode();(privatepath/'rows.json').write_bytes(raw);(privatepath/'rows.json').chmod(0o600)
 result={'historical_receipts':{n:h(BASE/n) for n in ['registration.json','private-input.json','private-report.json']},'sources':{str(p.relative_to(ROOT)):h(p) for p in [Path(__file__),ROOT/'src/nerve_awim/memory_gateway/scientific_family_b_v4.py',ROOT/'src/nerve_awim/memory_gateway/scientific_family_b_v5.py',ROOT/'src/nerve_awim/memory_gateway/scientific_family_b_adapter.py']},'table':dict(table),'private_rows_sha256':sha256(raw).hexdigest(),'model_calls':0,'holdout_access':False,'post_model_only':False,'reason':'v4 uses model output for every eligible answer; v5 bypasses inference and selects value and source from parsed evidence for ALL eligible answers. Raw outputs are replayed through v4; v5 ignores them by design.','conservative_affected_strata':['supported-measurement','measurement-decoy','entity-decoy','multi-source-agreement','stale-vs-current','format-variant-agreement'],'unaffected_within_valid_family_B_contract':['unit-mismatch','conflict','dissenter']}
 with OUT.open('x') as f:json.dump(result,f,sort_keys=True,indent=2);f.write('\n')
 print(json.dumps(result,indent=2))
if __name__=='__main__':
 def deny(*a,**kw):raise RuntimeError('offline only')
 with patch.object(socket.socket,'connect',deny),patch.object(socket,'create_connection',deny):run()
