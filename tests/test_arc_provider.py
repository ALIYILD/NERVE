import unittest
from nerve_awim.arc_provider import NativeDecisionProvider


class ArcProviderTests(unittest.TestCase):
    def receipt(self, value=None):
        return dict(ok=True, requested_model='configured:free', tools=0, value=value or {'tool': 'no-action'})

    def test_off_by_default_and_bounded_failure_accounting(self):
        calls=[]
        def native(*args, **kwargs):
            calls.append(kwargs); raise TimeoutError('private provider error')
        adapter=NativeDecisionProvider(object(), native)
        with self.assertRaises(PermissionError): adapter({})
        self.assertEqual(calls, [])
        adapter=NativeDecisionProvider(object(), native, enabled=True)
        for _ in range(2):
            with self.assertRaisesRegex(RuntimeError, 'configured provider unavailable'): adapter({})
        with self.assertRaisesRegex(RuntimeError, 'budget exhausted'): adapter({})
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(c['max_tokens']==2048 for c in calls))

    def test_paid_tool_using_and_ambiguous_json_outputs_fail(self):
        for receipt in (dict(ok=True,requested_model='paid',tools=0,value={}),
                        dict(ok=True,requested_model='model:free',tools=1,value={}),
                        self.receipt('{"tool":"safe","tool":"unsafe"}')):
            adapter=NativeDecisionProvider(object(),lambda *a,**k:receipt, enabled=True)
            with self.assertRaises((ValueError,RuntimeError)): adapter({})

    def test_uses_injected_existing_transport_without_endpoint_or_credentials(self):
        seen=[]; host=object()
        def native(actual,profile,prompt,**kw):
            self.assertIs(actual, host); self.assertEqual(profile,'qa-release')
            seen.append(prompt); return self.receipt({'tool':'request-information'})
        adapter=NativeDecisionProvider(host,native,enabled=True)
        self.assertEqual(adapter({'evidence_refs':[]})['tool'],'request-information')
        self.assertIn('Missing facts remain unknown',seen[0])
        self.assertIsNone(adapter.usage[0]['cost_usd'])
