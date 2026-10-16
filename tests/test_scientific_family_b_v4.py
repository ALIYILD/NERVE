import copy
import unittest
from nerve_awim.memory_gateway import scientific_family_b_adapter as base
from nerve_awim.memory_gateway import scientific_family_b_v4 as candidate
from nerve_awim.memory_gateway.scientific_candidates import _hash

QUERY="What is sample N0123456789abcdef's mass in mg?"

def record(source,entity='N0123456789abcdef',measurement='mass',value='12.0',current=True):
    result={'source_id':source,'content':f'For {entity}, the {measurement} measurement was {value} mg.','version':1,'current':current,'timestamp':'2026-10-16T00:00:00Z'}
    result['content_sha256']=_hash(result)
    return result

class CandidateTests(unittest.TestCase):
    def test_schema_only_preserves_all_decoys_and_multiple_supporting_sources(self):
        evidence=[record('z'),record('quantity-decoy',measurement='dry mass',value='90'),record('entity-decoy',entity='N0123456789abcdee',value='80'),record('old',value='70',current=False),record('a',value='12')]
        original=copy.deepcopy(evidence);before=base.prepare(QUERY,evidence,'adapted_v1');after=candidate.prepare(QUERY,evidence)
        self.assertEqual(after['schema']['properties']['source_id']['enum'],['z','a'])
        restored=copy.deepcopy(after);restored['schema']['properties']['source_id']['enum']=before['schema']['properties']['source_id']['enum']
        self.assertEqual(restored,before);self.assertEqual(evidence,original)
        self.assertEqual(set(after['schema']['properties']),{'source_id','unit','value'})
    def test_conflict_and_no_matching_evidence_unchanged(self):
        for evidence in ([record('a'),record('b',value='13')],[record('decoy',measurement='dry mass')]):
            self.assertEqual(candidate.prepare(QUERY,evidence),base.prepare(QUERY,evidence,'adapted_v1'))
    def test_wrong_value_is_never_repaired(self):
        prepared=candidate.prepare(QUERY,[record('a')]);decoded=base.decode('{"value":999,"unit":"mg","source_id":"a"}',prepared)
        self.assertEqual(decoded['value'],'999')
    def test_original_source_order_and_numeric_lexemes_preserved(self):
        evidence=[record('z',value='12.000'),record('a',value='12')];prepared=candidate.prepare(QUERY,evidence)
        self.assertEqual([r['value'] for r in prepared['records']],['12.000','12'])
        self.assertEqual(prepared['schema']['properties']['source_id']['enum'],['z','a'])

if __name__=='__main__':unittest.main()
