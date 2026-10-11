import ssl
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from nerve_awim.claude_pilot import tls_context


class ClaudeTransportTLSTests(unittest.TestCase):
    def test_system_trust_preserves_verified_context(self):
        with patch('nerve_awim.claude_pilot.ssl.get_default_verify_paths',return_value=SimpleNamespace(cafile='/trusted',capath=None)), \
             patch('nerve_awim.claude_pilot.ssl.create_default_context',return_value='verified') as create:
            self.assertEqual(tls_context(),'verified')
            create.assert_called_once_with()

    def test_framework_python_uses_explicit_ca_bundle(self):
        bundle=SimpleNamespace(where=lambda:'/trusted/certifi.pem')
        with patch('nerve_awim.claude_pilot.ssl.get_default_verify_paths',return_value=SimpleNamespace(cafile=None,capath=None)), \
             patch.dict('sys.modules',{'certifi':bundle}), \
             patch('nerve_awim.claude_pilot.ssl.create_default_context',return_value='verified') as create:
            self.assertEqual(tls_context(),'verified')
            create.assert_called_once_with(cafile='/trusted/certifi.pem')

    def test_real_context_requires_hostname_and_certificate_validation(self):
        context=tls_context()
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode,ssl.CERT_REQUIRED)
