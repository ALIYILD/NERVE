import hashlib,json,socket,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from nerve_awim.memory_gateway.scientific_family_b_v5 import decide
ENTITY='N0123456789abcdef';QUERY=f"What is sample {ENTITY}'s mass in mg?"
def record(source,value='1.0',entity=ENTITY,measurement='mass',unit='mg',current=True):
 r={'source_id':source,'content':f'For {entity}, the {measurement} measurement was {value} {unit}.','current':current,'version':2 if current else 1,'timestamp':'2026-10-16T00:00:00Z'}
 r['content_sha256']=hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest();return r
class Tests(unittest.TestCase):
 def test_numeric_equality_and_order(self):
  rows=[record('z','01.0'),record('a','1.00'),record('b','1')]
  with patch.object(socket.socket,'connect',side_effect=AssertionError('no model/network')):
   for order in (rows,rows[::-1]):
    result=decide(QUERY,order);self.assertEqual(result['source_id'],'a');self.assertEqual(result['value'],'1.00')
 def test_dissenter_not_majority(self):self.assertEqual(decide(QUERY,[record('a'),record('b'),record('c','1.1')])['status'],'abstain')
 def test_stale_smallest_source_excluded(self):self.assertEqual(decide(QUERY,[record('a','1.1',current=False),record('z')])['source_id'],'z')
 def test_decoy_filters_before_source_selection(self):
  rows=[record('a',entity='N0123456789abcdee'),record('b',measurement='dry mass'),record('c',unit='g'),record('z')]
  self.assertEqual(decide(QUERY,rows)['source_id'],'z')
 def test_no_conversion(self):self.assertEqual(decide(QUERY,[record('a',unit='g')])['status'],'abstain')
 def test_bad_provenance_fails_closed(self):
  r=record('a');r['content']='unregistered grammar';self.assertEqual(decide(QUERY,[r])['status'],'abstain')
 def test_bound_and_empty(self):
  self.assertEqual(decide(QUERY,[])['status'],'abstain');self.assertEqual(decide(QUERY,[record(str(i)) for i in range(13)])['status'],'abstain')
if __name__=='__main__':unittest.main()
