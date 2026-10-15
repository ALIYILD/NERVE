"""Synthetic two-stage policy: exact evidence gate, then forced compact JSON.

No labels or expected answers enter preparation. This is host rule execution,
not learned model capability. Local opener restrictions reuse the existing adapter.
"""
from hashlib import sha256
from decimal import Decimal
import json
from urllib.request import Request
from . import scientific_compact_dev_transport as compact
from . import scientific_substrate_calibration_transport as calibration

grammar=compact.grammar
MODEL,ORIGIN=compact.MODEL,compact.ORIGIN
SEED=20261015
MAX_OUTPUT_TOKENS=128
TIMEOUT_SECONDS=30
SYSTEM='Use only facts. Return JSON with value, unit, source_id for the queried entity/measurement/unit. Use a listed source alias. No unit conversion or prose.'
_FROZEN=(MODEL,ORIGIN,SEED,MAX_OUTPUT_TOKENS,TIMEOUT_SECONDS,SYSTEM)


def sources():
    from . import scientific_substrate_calibration as prior
    result=prior.sources()
    name='src/nerve_awim/memory_gateway/scientific_candidate_v3.py'
    result[name]=sha256((prior.pilot.ROOT/name).read_bytes()).hexdigest()
    return result


def _rules():
    compact._policy()
    if (MODEL,ORIGIN,SEED,MAX_OUTPUT_TOKENS,TIMEOUT_SECONDS,SYSTEM)!=_FROZEN:raise ValueError('v3_policy_changed')


def gate(query,evidence):
    _rules();grammar._inputs(query,evidence)
    requested=grammar.QUERY.fullmatch(query)
    if requested is None:return dict(eligible=False,reason='unsupported_query')
    current=[r for r in evidence if r['current']]
    if not current:return dict(eligible=False,reason='missing_evidence')
    parsed=[grammar.FACT.fullmatch(r['content']) for r in current]
    if any(p is None for p in parsed):return dict(eligible=False,reason='unsupported_evidence')
    target=[p.groups() for p in parsed if p.group(1)==requested.group(1)]
    if not target:return dict(eligible=False,reason='entity_mismatch')
    matching=[p for p in target if p[1]=='mass' and p[3]=='mg']
    if not matching:return dict(eligible=False,reason='unit_or_measurement_mismatch')
    if len({Decimal(p[2]) for p in matching})>1:return dict(eligible=False,reason='conflict')
    return dict(eligible=True,reason='matching_current_evidence')


def prepare(query,evidence,*,arm='candidate'):
    _rules();grammar._inputs(query,evidence)
    if type(arm) is not str or arm not in ('candidate','baseline'):raise ValueError('fixed_arm_required')
    decision=gate(query,evidence)
    current=[r for r in evidence if r['current']]
    small=compact.prepare(query,current) if current and decision['reason'] not in ('unsupported_query','unsupported_evidence') else None
    if arm=='baseline' and small is None:raise ValueError('supported_baseline_input_required')
    schema=None
    if arm=='candidate' and decision['eligible']:
        schema={'type':'object','properties':{'value':{'type':'number'},'unit':{'type':'string','enum':sorted({r['unit'] for r in small['aliases'].values()})},
                'source_id':{'type':'string','enum':sorted(small['aliases'])}},'required':['value','unit','source_id'],'additionalProperties':False}
    return dict(arm=arm,query=query,evidence=json.loads(compact._canonical(evidence)),
        route='model' if arm=='baseline' or decision['eligible'] else 'deterministic_abstention',gate_reason=decision['reason'],
        system=SYSTEM if arm=='candidate' else compact.SYSTEM,user=small['user'] if small else '',
        aliases=small['aliases'] if small else {},entity_aliases=small['entity_aliases'] if small else {},schema=schema,
        input_sha256=grammar.candidates._hash({'query':query,'evidence':evidence}))


def _checked(prepared):
    if type(prepared) is not dict:raise ValueError('prepared_v3_required')
    fixed=prepare(prepared['query'],prepared['evidence'],arm=prepared['arm'])
    if compact._canonical(fixed)!=compact._canonical(prepared):raise ValueError('v3_preparation_changed')
    return fixed


def decode(raw,prepared):
    fixed=_checked(prepared)
    if type(raw) is not str or not 1<=len(raw)<=16384:raise ValueError('bounded_raw_required')
    if fixed['route']=='deterministic_abstention':
        if raw!='ABSTAIN':raise ValueError('deterministic_abstention_required')
        return dict(grammar.ABSTAIN)
    if fixed['arm']=='baseline':return compact.decode(raw,compact.prepare(fixed['query'],[r for r in fixed['evidence'] if r['current']]))
    try:value=json.loads(raw,object_pairs_hook=compact._object,parse_float=Decimal,parse_int=Decimal,
                         parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite')))
    except (ValueError,RecursionError) as error:raise ValueError('strict_json_required') from error
    if (type(value) is not dict or set(value)!={'value','unit','source_id'} or type(value['value']) is not Decimal
            or not value['value'].is_finite() or abs(value['value'].adjusted())>24 or value['value'].as_tuple().exponent < -24
            or type(value['unit']) is not str or value['unit'] not in fixed['schema']['properties']['unit']['enum']
            or type(value['source_id']) is not str or value['source_id'] not in fixed['aliases']):raise ValueError('strict_schema_required')
    source=fixed['aliases'][value['source_id']]
    return dict(status='answer',entity=source['entity'],measurement=source['measurement'],value=format(value['value'],'f'),
                unit=value['unit'],source_id=source['source_id'])


def schema_valid(raw,prepared):
    fixed=_checked(prepared)
    if fixed['arm']!='candidate' or fixed['route']!='model':return None
    try:decode(raw,fixed)
    except ValueError:return False
    return True


def run(prepared,*,authorize,timeout_seconds=30):
    if not callable(authorize) or type(timeout_seconds) not in (int,float) or timeout_seconds!=TIMEOUT_SECONDS:raise ValueError('fixed_host_transport_required')
    fixed=_checked(prepared);binding=compact._canonical(fixed)
    def check():
        authorize();_rules()
        if compact._canonical(prepared)!=binding:raise ValueError('v3_preparation_changed')
    check()
    result=dict(model=MODEL,origin=ORIGIN,model_sampling_seed=SEED,input_sha256=fixed['input_sha256'],
                review_required=True,synthetic_only=True,model_weights_trained=False,route=fixed['route'])
    if fixed['route']=='deterministic_abstention':
        check();return dict(result,raw_output='ABSTAIN',usage=None,finish_reason=None,model_calls=0)
    payload=dict(model=MODEL,temperature=0,seed=SEED,stream=False,max_tokens=MAX_OUTPUT_TOKENS,
                 messages=[{'role':'system','content':fixed['system']},{'role':'user','content':fixed['user']}])
    if fixed['schema'] is not None:
        payload['response_format']={'type':'json_schema','json_schema':{'name':'scientific_measurement','strict':True,'schema':fixed['schema']}}
    request=Request(ORIGIN+'/v1/chat/completions',data=json.dumps(payload).encode(),method='POST',headers={'Content-Type':'application/json','Accept':'application/json'})
    with calibration._adapter(float(timeout_seconds))._opener.open(request,timeout=float(timeout_seconds)) as response:raw=response.read(65537)
    if len(raw)>65536:raise ValueError('bounded_response_required')
    value=json.loads(raw,object_pairs_hook=compact._object)
    if type(value) is not dict or value.get('model')!=MODEL or type(value.get('choices')) is not list or len(value['choices'])!=1:raise ValueError('response_identity_required')
    choice=value['choices'][0]
    if type(choice) is not dict:raise ValueError('choice_required')
    message=choice.get('message')
    if (choice.get('finish_reason') not in ('stop','length') or type(message) is not dict or message.get('role')!='assistant'
        or message.get('tool_calls') or message.get('function_call') or type(message.get('content')) is not str
        or not 1<=len(message['content'])<=16384):raise ValueError('bounded_completion_required')
    usage=value.get('usage')
    keys=('prompt_tokens','completion_tokens','total_tokens')
    if type(usage) is not dict or not set(keys)<=set(usage):raise ValueError('actual_usage_required')
    usage={k:usage[k] for k in keys}
    if (any(type(v) is not int or not 0<=v<=10000000 for v in usage.values()) or usage['completion_tokens']>MAX_OUTPUT_TOKENS
        or usage['total_tokens']!=usage['prompt_tokens']+usage['completion_tokens']):raise ValueError('actual_usage_required')
    try:check()
    except Exception as error:
        error.unscored_raw_response=dict(raw_output=message['content'],usage=usage,finish_reason=choice['finish_reason'],reason='post_response_authorization_failed')
        raise
    return dict(result,raw_output=message['content'],usage=usage,finish_reason=choice['finish_reason'],model_calls=1)
