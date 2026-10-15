"""Signed-owner HTTP recovery against real ledger; controller is a test double."""
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import Mock
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from nerve_guardian.auth import OwnerVerifier
from nerve_guardian.core import Guardian
from nerve_guardian.demo import FixtureProbe
from nerve_guardian.store import Store
from nerve_guardian.web import create_server

class HTTPRecoveryTests(unittest.TestCase):
    def test_signed_mfa_owner_recovery_and_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);pin=root/'pin';pin.write_text('approved')
            controller=Mock();controller.contain.return_value={'verified':True};controller.verify.return_value={'verified':True};controller.restart.return_value={'verified':True}
            engine=Guardian(Store(root/'state'),controller,FixtureProbe(pin),tenants=['demo'],owners={'human-owner':'demo'},armed=True,synthetic=True)
            pin.write_text('tampered');incident=engine.tick('demo')['incidents'][0]['id']
            key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
            public=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
            verifier=OwnerVerifier(issuer='https://idp.example.invalid',audience='guardian',public_keys={'test':public},owners={'human-owner':'demo'})
            server=create_server(engine,verifier);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            def token(jti,subject='human-owner'):
                now=int(time.time())
                return jwt.encode({'iss':'https://idp.example.invalid','aud':'guardian','sub':subject,'exp':now+120,'iat':now,'nbf':now,'auth_time':now,'jti':jti,'amr':['mfa']},key,algorithm='RS256',headers={'kid':'test'})
            def post(path,bearer,body):
                request=urllib.request.Request('http://127.0.0.1:'+str(server.server_port)+path,data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+bearer,'Content-Type':'application/json'})
                try:
                    with urllib.request.urlopen(request,timeout=3) as response:return response.status,json.loads(response.read())
                except urllib.error.HTTPError as error:return error.code,json.loads(error.read())
            try:
                body={'incident_id':incident,'cause_reference':'reviewed-test-repair'}
                self.assertEqual(post('/api/request-restart',token('unauthorized-token','agent'),body)[0],403)
                status,result=post('/api/request-restart',token('request-token'),body);self.assertEqual(status,200)
                pin.write_text('approved')
                approve={'incident_id':incident,'request_id':result['id']};bearer=token('approval-token')
                status,result=post('/api/approve-restart',bearer,approve)
                self.assertEqual(status,200);self.assertEqual(result['status'],'RESOLVED')
                self.assertEqual(post('/api/approve-restart',bearer,approve)[0],403)
                self.assertEqual(controller.restart.call_count,1)
                self.assertTrue(any(r['kind']=='unauthorized_restart_attempt' for r in engine.audit('demo')))
            finally:server.shutdown();server.server_close();thread.join(timeout=2)
