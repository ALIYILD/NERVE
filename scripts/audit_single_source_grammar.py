"""Exhaustive finite production/boundary audit, NOT exhaustive model verification."""
import sys,json,itertools,socket
from pathlib import Path
from hashlib import sha256
from decimal import Decimal
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nerve_awim.memory_gateway import scientific_task_bank_v3 as bank,scientific_family_b_adapter as a,scientific_family_b_v4 as v4,scientific_family_b_v5 as v5
STRATA=('supported-measurement','measurement-decoy','entity-decoy','stale-vs-current')
VALUES=('0','1','1.0','01.000','999999999999','0.000000000001','999999999999.999999999999')
def run():
 counts={s:{'production_boundary_cases':0,'correct_raw_semantic_agreement':0,'correct_raw_byte_agreement':0,'schema_valid_wrong_value_counterexamples':0} for s in STRATA}
 for s in STRATA:
  seedtask=bank.item(bytes(32),'dev',s,7766)
  target=seedtask['expected']['entity']
  for template,value,position in itertools.product(range(3),VALUES,range(len(seedtask['evidence']))):
   task=json.loads(json.dumps(seedtask));match=next(r for r in task['evidence'] if (lambda p:p['entity']==target and p['measurement']=='mass' and p['current'])(a.parse_record(r)))
   if template==0:match['content']=f'Mass of sample {target}: {value} mg (current).'
   elif template==1:match['content']=f'For {target}, the mass measurement was {value} mg.'
   else:match['content']=f'The laboratory recorded {value} mg as mass for {target}.'
   match['content_sha256']=bank.digest({k:v for k,v in match.items() if k!='content_sha256'})
   task['evidence'].remove(match);task['evidence'].insert(position,match)
   p=v4.prepare(task['query'],task['evidence']);b=v5.decide(task['query'],task['evidence']);amount=format(Decimal(value),'f')
   # Build exact JSON decimal text, avoiding float rounding and leading-zero invalid JSON.
   raw='{"value":'+amount+',"unit":"mg","source_id":'+json.dumps(match['source_id'])+'}'
   decoded=a.decode(raw,p);c=counts[s];c['production_boundary_cases']+=1
   c['correct_raw_semantic_agreement']+=all(decoded[k]==b[k] for k in decoded if k!='value') and Decimal(decoded['value'])==Decimal(b['value'])
   c['correct_raw_byte_agreement']+=bank.canonical(decoded)==bank.canonical(b)
   wrong='{"value":'+('1' if Decimal(value)==0 else '0')+',"unit":"mg","source_id":'+json.dumps(match['source_id'])+'}'
   assert a.decode(wrong,p)!=b;c['schema_valid_wrong_value_counterexamples']+=1
 replay=json.loads((ROOT/'docs/galahad/evidence/gate-v3_1-dev-seam-replay.json').read_text())['table']['format-variant-agreement']
 result={'full_v4_v5_equivalence_proven':False,'model_calls':0,'bank_reserve_access':False,'enumeration':'All three target sentence productions x seven registered numeric boundary representatives x every target-list position, for four representative generated evidence contexts. Does NOT enumerate all identities, values, decoy combinations, source permutations or model executions.','grammar_bound':'Templates are finite; the bounded instantiated language is enormous. V4 output value is model supplied and not constrained to the evidence value by its schema. Grammar enumeration alone cannot prove end-to-end equivalence.','counts':counts,'proof_obligation_remaining':'Formal verification of the model output function, or exhaustive actual model evaluation over all admissible instantiated inputs; neither performed. Supplying a correct raw answer is a conditional test, not such proof.','counterexample_scope':'Different rule-set outputs for schema-valid supplied raw values; does not assert that the actual model emits these counterexamples.','format_variant':{'items':100,'byte_identical':replay['byte_identical'],'representational_only_differences':replay['numeric_semantically_equal']-replay['byte_identical'],'decisional_differences':100-replay['numeric_semantically_equal'],'wrong_source_decisions':replay['changed_fields']['source_id'],'numeric_value_string_changes_total_overlapping':replay['changed_fields']['value']},'source_sha256':{str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'src/nerve_awim/memory_gateway/scientific_family_b_v4.py',ROOT/'src/nerve_awim/memory_gateway/scientific_family_b_v5.py',ROOT/'src/nerve_awim/memory_gateway/scientific_family_b_adapter.py',ROOT/'src/nerve_awim/memory_gateway/scientific_task_bank_v3.py']}}
 with (ROOT/'docs/galahad/evidence/bank-v5-equivalence-audit.json').open('x') as f:json.dump(result,f,sort_keys=True,indent=2);f.write('\n')
 print(json.dumps(result,indent=2))
if __name__=='__main__':
 def deny(*a,**kw):raise RuntimeError('network forbidden')
 with patch.object(socket.socket,'connect',deny),patch.object(socket,'create_connection',deny):run()
