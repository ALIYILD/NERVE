import json
import threading
import time
import unittest
import urllib.request
import urllib.error
from nerve_guardian.auth import OwnerVerifier, AuthorizationError
from nerve_guardian.web import create_server


class AdminTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import jwt
        from cryptography.hazmat.primitives.asymmetric import rsa
        cls.jwt = jwt
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def setUp(self):
        self.verifier = OwnerVerifier(issuer='https://owner.example', audience='guardian', public_keys={'key': self.key.public_key()}, owners={'owner': 'tenant-a'})

    def token(self, **changes):
        now = int(time.time())
        claims = dict(iss='https://owner.example', aud='guardian', sub='owner', exp=now+600, iat=now, nbf=now, auth_time=now, jti='test-token-123', amr=['mfa'])
        claims.update(changes)
        return self.jwt.encode(claims, self.key, algorithm='RS256', headers={'kid':'key'})

    def test_pinned_owner_mfa_and_freshness(self):
        self.assertEqual(self.verifier.verify(self.token(), restart=True).tenant, 'tenant-a')
        for changes in ({'sub':'agent'}, {'amr':['pwd']}, {'aud':'nerve'}, {'exp':1}, {'auth_time':int(time.time())-301}, {'jti':''}, {'nbf':int(time.time())+60}):
            with self.assertRaises(AuthorizationError):
                self.verifier.verify(self.token(**changes), restart=True)

    def test_owner_subject_does_not_authorize_delegated_or_machine_token(self):
        for claims in ({'act': {'sub': 'agent'}}, {'may_act': {}}, {'gty': 'client-credentials'},
                       {'grant_type': 'client_credentials'}, {'identity_type': 'agent'},
                       {'is_service_account': True}, {'is_agent': True}):
            with self.assertRaises(AuthorizationError):
                self.verifier.verify(self.token(**claims), restart=True)

    def test_loopback_server_authorization_and_xss(self):
        class Engine:
            called = False
            def snapshot(self, tenant):
                return {'tenant':tenant, 'gaps':['<script>alert(1)</script>'], 'status':'UNKNOWN'}
            def keep_stopped(self, *args):
                self.called = True
                return {'ok':True}
        engine = Engine()
        server = create_server(engine, self.verifier)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        root = 'http://127.0.0.1:'+str(server.server_port)
        try:
            for headers in ({}, {'X-Owner':'owner'}, {'Authorization':'Bearer invalid'}):
                request = urllib.request.Request(root+'/api/keep-stopped', data=b'{"incident_id":"i"}', headers={**headers,'Content-Type':'application/json'})
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(request)
                self.assertEqual(error.exception.code, 403)
            self.assertFalse(engine.called)
            with urllib.request.urlopen(urllib.request.Request(root+'/api/snapshot',headers={'Authorization':'Bearer '+self.token()})) as response:
                self.assertEqual(json.load(response)['tenant'],'tenant-a')
                self.assertEqual(response.headers['Cache-Control'],'no-store')
                self.assertIn("frame-ancestors 'none'", response.headers['Content-Security-Policy'])
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(root+'/api/snapshot?token='+self.token())
            with urllib.request.urlopen(root+'/app.js') as response:
                script = response.read().decode()
                self.assertNotIn('innerHTML', script)
                self.assertNotIn('localStorage', script)
                self.assertIn('textContent', script)
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_remote_bind_denied(self):
        with self.assertRaises(ValueError):
            create_server(None, self.verifier, host='0.0.0.0')
