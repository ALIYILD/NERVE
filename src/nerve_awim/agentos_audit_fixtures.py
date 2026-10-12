"""Hand-authored, simulated development controls for typed audit decisions.

These cases describe invented observations, not production incidents. They are
public development fixtures, not a held-out evaluation, independent trial, or
train/selection/final split. Expected decisions and citations are authored here
without calling the oracle. Host-veto semantics are outside this typed schema.
Invalid provenance cycles belong in validator tests, not valid decision cases.
"""

_SCHEMA = 'agentos-audit-evidence-v1'
_MODEL = 'simulated/primary:free'
_PROVIDER = 'simulated-provider'


def _source(ident, kind, fields, *, model=_MODEL, provider=_PROVIDER,
            observed_at=1000, derived_from=()):
    return dict(id=ident, kind=kind, model=model, provider=provider,
                observed_at=observed_at, derived_from=list(derived_from), fields=fields)


def _case(ident, family, claim_kind, sources, decision, citations):
    claim = dict(kind=claim_kind, model=_MODEL, provider=_PROVIDER, at=1000, max_age=100)
    if claim_kind == 'execution_success':
        claim['request_id'] = 'request-target'
    return dict(id=ident, family=family,
                bundle=dict(schema=_SCHEMA, simulated=True, claim=claim, sources=sources),
                expected=dict(decision=decision, citations=citations))


def development_cases():
    """Return fresh copies of fourteen public, simulated development controls.

    Unknown with no citations means no applicable direct observation. Conflicting
    applicable observations produce unknown with both sources explicitly cited.
    All gold fields below are explicit, including observation identity and time.
    """
    return [
        _case('dev-credential-is-not-execution', 'capability-separation', 'execution_success', [
            _source('key-probe', 'credential_probe', {'present': True}),
        ], 'unknown', []),
        _case('dev-listing-is-not-execution', 'capability-separation', 'execution_success', [
            _source('model-list', 'catalog', {'listed': True}),
        ], 'unknown', []),
        _case('dev-worker-qa-echo-is-not-proof', 'derived-assertion', 'execution_success', [
            _source('worker-claim', 'assertion', {'text': 'Simulated worker says the request succeeded.'}),
            _source('qa-echo', 'summary', {'text': 'Simulated QA repeats the worker claim.'},
                    derived_from=('worker-claim',)),
        ], 'unknown', []),
        _case('dev-fallback-is-not-primary', 'model-identity', 'execution_success', [
            _source('fallback-receipt', 'execution_receipt',
                    {'request_id': 'request-target', 'success': True}, model='simulated/fallback:free'),
        ], 'unknown', []),
        _case('dev-exact-request-succeeded', 'execution-result', 'execution_success', [
            _source('success-receipt', 'execution_receipt',
                    {'request_id': 'request-target', 'success': True}),
        ], 'supported', [
            {'source_id': 'success-receipt', 'fields': [
                'fields.request_id', 'fields.success', 'model', 'observed_at', 'provider']},
        ]),
        _case('dev-exact-request-failed', 'execution-result', 'execution_success', [
            _source('failure-receipt', 'execution_receipt',
                    {'request_id': 'request-target', 'success': False}),
        ], 'contradicted', [
            {'source_id': 'failure-receipt', 'fields': [
                'fields.request_id', 'fields.success', 'model', 'observed_at', 'provider']},
        ]),
        _case('dev-zero-pricing-at-freshness-boundary', 'pricing-freshness', 'zero_price', [
            _source('boundary-price', 'pricing', {'input_usd': 0, 'output_usd': 0}, observed_at=900),
        ], 'supported', [
            {'source_id': 'boundary-price', 'fields': [
                'fields.input_usd', 'fields.output_usd', 'model', 'observed_at', 'provider']},
        ]),
        _case('dev-free-suffix-with-paid-output', 'pricing-value', 'zero_price', [
            _source('paid-output-price', 'pricing', {'input_usd': 0, 'output_usd': 0.002}),
        ], 'contradicted', [
            {'source_id': 'paid-output-price', 'fields': [
                'fields.input_usd', 'fields.output_usd', 'model', 'observed_at', 'provider']},
        ]),
        _case('dev-expired-zero-pricing', 'pricing-freshness', 'zero_price', [
            _source('expired-price', 'pricing', {'input_usd': 0, 'output_usd': 0}, observed_at=899),
        ], 'unknown', []),
        _case('dev-conflicting-current-prices', 'conflicting-observations', 'zero_price', [
            _source('price-a-zero', 'pricing', {'input_usd': 0, 'output_usd': 0}, observed_at=950),
            _source('price-b-paid', 'pricing', {'input_usd': 0.001, 'output_usd': 0}, observed_at=1000),
        ], 'unknown', [
            {'source_id': 'price-a-zero', 'fields': [
                'fields.input_usd', 'fields.output_usd', 'model', 'observed_at', 'provider']},
            {'source_id': 'price-b-paid', 'fields': [
                'fields.input_usd', 'fields.output_usd', 'model', 'observed_at', 'provider']},
        ]),
        _case('dev-key-probe-proves-only-key-presence', 'credential-presence', 'credential_present', [
            _source('local-key-probe', 'credential_probe', {'present': True}),
        ], 'supported', [
            {'source_id': 'local-key-probe', 'fields': [
                'fields.present', 'model', 'observed_at', 'provider']},
        ]),
        _case('dev-model-explicitly-not-listed', 'catalog-membership', 'catalog_listed', [
            _source('negative-listing', 'catalog', {'listed': False}),
        ], 'contradicted', [
            {'source_id': 'negative-listing', 'fields': [
                'fields.listed', 'model', 'observed_at', 'provider']},
        ]),
        _case('dev-other-request-is-not-target', 'request-identity', 'execution_success', [
            _source('other-request-receipt', 'execution_receipt',
                    {'request_id': 'request-other', 'success': True}),
        ], 'unknown', []),
        _case('dev-other-provider-is-not-target', 'provider-identity', 'execution_success', [
            _source('other-provider-receipt', 'execution_receipt',
                    {'request_id': 'request-target', 'success': True}, provider='simulated-other-provider'),
        ], 'unknown', []),
    ]
