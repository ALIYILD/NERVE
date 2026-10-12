"""Galahad gateway retrieval and text/API exports preserve scoped uncertainty."""
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest

from nerve_awim.arc_workflows import build_workflow_engine
from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger
from nerve_awim.memory_gateway.gateway import MemoryGateway
from nerve_awim.memory_gateway.contracts import MemoryScope, MemoryRequest
from nerve_awim.uncertainty.ledger import Ledger
from nerve_awim.uncertainty.contracts import Claim
from nerve_awim.uncertainty.adapters import UncertaintyAdapter


class MemoryUncertaintyIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'learning.sqlite3'
        self.c=build_workflow_engine(self.path)
        self.ledger=Ledger(self.c['engine']);actor=self.c['actor']
        for ident,value in [('claim-yes',True),('claim-no',False)]:
            source=self.ledger.register_source(actor,'source-'+ident,{'synthetic':True,'value':value})
            self.ledger.add_claim(actor,Claim(ident,actor.tenant,'task','subject','status',value,**source))
        self.conflict=self.ledger.detect(actor,'task')[0]
        self.adapter=UncertaintyAdapter(self.ledger,actor,task_id='task',dependency_claim_ids=['claim-yes'])
        self.authority=MemoryAuthority();self.memory=TrustedMemoryLedger(self.path,self.authority)
        self.reader=self.authority.issue('synthetic','arc-workflow',permissions=('read','propose'))
        self.reviewer=self.authority.issue('synthetic','arc-workflow',permissions=('read','approve','delete'))
        self.scope=MemoryScope('synthetic','arc-workflow','planning')
        self.mid=self.memory.propose(self.reader,context='planning',content='Synthetic approved memory says status is certain.',source_id='memory-source')
        self.memory.decide(self.reviewer,self.mid,approve=True,evaluator_id='synthetic-review',score=.9)
        self.gateway=MemoryGateway(self.memory,uncertainty=self.adapter)

    def request(self,**kwargs):return MemoryRequest(self.scope,'synthetic',**kwargs)

    def test_approved_memory_does_not_override_conflict_in_text_and_api(self):
        result=self.gateway.retrieve(self.reader,self.request())
        self.assertEqual([r.memory_id for r in result.records],[self.mid])
        self.assertIn(self.conflict.conflict_id,result.uncertainty['open_conflict_ids'])
        self.assertIn(self.conflict.conflict_id,result.context_text)
        self.assertFalse(asdict(result)['guidance_authority'])
        self.assertEqual(asdict(result)['uncertainty'],result.uncertainty)
        self.assertEqual(self.ledger.get_conflict(self.c['actor'],self.conflict.conflict_id).status,'confirmed_open')

    def test_restart_adapter_omission_and_custom_ranker_bypass_fail_closed(self):
        self.gateway.retrieve(self.reader,self.request())
        class BypassRanker:
            ledger=self.memory
            def retrieve(inner,*args,**kwargs):return [self.memory.status(self.reader,self.mid)]
        for gateway in (MemoryGateway(self.memory),MemoryGateway(self.memory,retriever=BypassRanker())):
            with self.assertRaises(PermissionError):gateway.retrieve(self.reader,self.request())
        reopened=build_workflow_engine(self.path)
        adapter=UncertaintyAdapter(Ledger(reopened['engine']),reopened['actor'],task_id='task',dependency_claim_ids=['claim-yes'])
        result=MemoryGateway(self.memory,uncertainty=adapter).retrieve(self.reader,self.request())
        self.assertIn(self.conflict.conflict_id,result.uncertainty['open_conflict_ids'])

    def test_revocation_revalidates_records_but_keeps_conflict(self):
        self.gateway.retrieve(self.reader,self.request())
        self.gateway.revoke(self.reviewer,self.mid,scope=self.scope,evaluator_id='revoke-review')
        result=self.gateway.retrieve(self.reader,self.request())
        self.assertEqual(result.records,())
        self.assertNotIn('status is certain',result.context_text)
        self.assertIn(self.conflict.conflict_id,result.context_text)

    def test_wrong_scope_and_revoked_uncertainty_actor_denied(self):
        other=self.authority.issue('other','arc-workflow',permissions=('read',))
        with self.assertRaises(PermissionError):self.gateway.retrieve(other,self.request())
        self.c['engine'].authority.revoke(self.c['actor'])
        with self.assertRaises(PermissionError):self.gateway.retrieve(self.reader,self.request())

    def test_adapter_outage_never_returns_raw_memory_fallback(self):
        from unittest.mock import patch
        self.gateway.retrieve(self.reader,self.request())
        with patch.object(self.adapter,'handoff',side_effect=RuntimeError('ledger unavailable')):
            with self.assertRaises(RuntimeError):self.gateway.retrieve(self.reader,self.request())
        with self.assertRaises(PermissionError):MemoryGateway(self.memory).retrieve(self.reader,self.request())

    def test_distinct_store_adapter_rejected(self):
        other=TrustedMemoryLedger(Path(self.tmp.name)/'other.sqlite3',self.authority)
        with self.assertRaises(PermissionError):MemoryGateway(other,uncertainty=self.adapter)

    def test_context_budget_cannot_silently_truncate_mandatory_state(self):
        with self.assertRaises(ValueError):self.gateway.retrieve(self.reader,self.request(max_context_chars=256))
        result=self.gateway.retrieve(self.reader,self.request(max_context_chars=4096))
        self.assertLessEqual(len(result.context_text),4096)
        self.assertIn(self.conflict.conflict_id,result.context_text)

    def test_http_and_reference_client_preserve_envelope_and_restart_denial(self):
        import io
        import json
        import time
        try:
            import jwt
            from cryptography.hazmat.primitives.asymmetric import rsa
        except ImportError:
            self.skipTest('PyJWT[crypto] required for signed HTTP boundary')
        from nerve_awim.oidc_v27 import PinnedOIDCVerifier
        from nerve_awim.memory_gateway.service import MemoryService, MemoryGrant
        from nerve_awim.memory_gateway.client import MemoryClient
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
        jwk.update(kid='synthetic', alg='RS256')
        verifier = PinnedOIDCVerifier(issuer='https://identity.test', audience='memory', jwks={'keys':[jwk]})
        grant = MemoryGrant('fixture', self.reader, self.scope, 'synthetic-clinic',
                            'synthetic-patient', frozenset({'reader'}))
        service = MemoryService(self.gateway, verifier=verifier, grants=[grant])
        now = int(time.time())
        token = jwt.encode(dict(sub='fixture', iss=verifier.issuer, aud='memory', iat=now-1,
            exp=now+60, roles=['nerve-memory-reader']), key, algorithm='RS256', headers={'kid':'synthetic'})
        body = json.dumps(dict(clinic_id='synthetic-clinic',patient_id='synthetic-patient',query='synthetic',limit=5)).encode()
        def request():
            status=[]
            env=dict(PATH_INFO='/v1/memory/query',REQUEST_METHOD='POST',CONTENT_TYPE='application/json',
                CONTENT_LENGTH=str(len(body)),HTTP_AUTHORIZATION='Bearer '+token)
            env['wsgi.input']=io.BytesIO(body)
            raw=b''.join(service(env, lambda code, headers:status.append(int(code.split()[0]))))
            return status[0],raw
        code,raw=request()
        self.assertEqual(code,200)
        payload=json.loads(raw)
        self.assertIn(self.conflict.conflict_id,payload['uncertainty']['open_conflict_ids'])
        self.assertFalse(payload['guidance_authority'])
        class OfflineTransport:
            def open(inner,*args,**kwargs):return io.BytesIO(raw)
        client=MemoryClient('https://memory.test',token)
        client._opener=OfflineTransport()
        self.assertEqual(client.query(clinic_id='synthetic-clinic',patient_id='synthetic-patient',query='synthetic'),payload)
        service.gateway=MemoryGateway(self.memory)
        self.assertEqual(request()[0],403)

    def test_optional_ranking_modes_use_explicit_scoped_fallback(self):
        for mode in ('semantic','adaptive'):
            result=self.gateway.retrieve(self.reader,self.request(mode=mode))
            self.assertEqual(result.fallback_reason,'uncertainty_scoped_lexical_fallback')
            self.assertIn(self.conflict.conflict_id,result.context_text)


if __name__=='__main__':unittest.main()
