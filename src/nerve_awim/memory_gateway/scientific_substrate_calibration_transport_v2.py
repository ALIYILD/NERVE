"""Three frozen local calibration interfaces; preserve bounded raw stop/length output."""
import json
from urllib.error import URLError
from urllib.request import Request
from . import scientific_compact_dev_transport as compact
from . import scientific_candidate_execution as original
from .inference import LocalInferenceAdapter
from .scientific_model_learning import MODEL,ORIGIN

ARMS=('compact','original','forced_answer')
SEED=20261015
MAX_OUTPUT_TOKENS=128
FORCED_SYSTEM='Use only facts. Return value|unit|source for the queried entity/measurement/unit. No unit conversion or prose.'
_FROZEN=(ARMS,SEED,MAX_OUTPUT_TOKENS,FORCED_SYSTEM,MODEL,ORIGIN)


class TransportTimeout(TimeoutError):
    """The HTTP open/read timed out; never an authorization/deadline failure."""


def _rules():
    compact._policy();original._rules()
    if (ARMS,SEED,MAX_OUTPUT_TOKENS,FORCED_SYSTEM,MODEL,ORIGIN)!=_FROZEN:raise ValueError('calibration_transport_changed')


def prepare(arm,query,evidence):
    _rules()
    if type(arm) is not str or arm not in ARMS:raise ValueError('registered_calibration_arm_required')
    small=compact.prepare(query,evidence)
    if arm=='original':
        prior=original.prepare(dict(original.candidates.SPACE['conflict_check']),query,evidence)
        system=prior['system']
        user=json.dumps({'query':query,'evidence_jsonl':'\n'.join(compact._canonical(r) for r in prior['evidence'])},ensure_ascii=True)
    else:system=compact.SYSTEM if arm=='compact' else FORCED_SYSTEM;user=small['user']
    return dict(arm=arm,query=query,evidence=json.loads(compact._canonical(evidence)),
        messages=[{'role':'system','content':system},{'role':'user','content':user}],input_sha256=small['input_sha256'])


def _adapter(timeout):
    return LocalInferenceAdapter(base_url=ORIGIN,model=MODEL,max_output_tokens=MAX_OUTPUT_TOKENS,
                                 timeout_seconds=min(90,timeout),runtime_profile='cpu_research')


def run(prepared,*,authorize,timeout_seconds=240):
    _rules()
    if not callable(authorize) or type(timeout_seconds) not in (int,float) or not 1<=timeout_seconds<=240:raise ValueError('bounded_host_transport_required')
    fixed=prepare(prepared['arm'],prepared['query'],prepared['evidence']);binding=compact._canonical(fixed)
    if compact._canonical(prepared)!=binding:raise ValueError('calibration_preparation_changed')
    authorize();_rules()
    if compact._canonical(prepared)!=binding:raise ValueError('calibration_preparation_changed')
    payload=dict(model=MODEL,temperature=0,seed=SEED,stream=False,max_tokens=MAX_OUTPUT_TOKENS,messages=fixed['messages'])
    request=Request(ORIGIN+'/v1/chat/completions',data=json.dumps(payload).encode(),method='POST',headers={'Content-Type':'application/json','Accept':'application/json'})
    try:
        with _adapter(float(timeout_seconds))._opener.open(request,timeout=float(timeout_seconds)) as response:raw=response.read(65537)
    except TimeoutError as error:raise TransportTimeout('socket_open_or_read_timeout') from error
    except URLError as error:
        if isinstance(error.reason,TimeoutError):raise TransportTimeout('socket_open_or_read_timeout') from error
        raise
    if len(raw)>65536:raise ValueError('bounded_model_response_required')
    value=json.loads(raw,object_pairs_hook=compact._object)
    if type(value) is not dict or value.get('model')!=MODEL or type(value.get('choices')) is not list or len(value['choices'])!=1:raise ValueError('calibration_response_shape')
    choice=value['choices'][0];message=choice.get('message')
    if (choice.get('finish_reason') not in ('stop','length') or type(message) is not dict or message.get('role')!='assistant'
            or message.get('tool_calls') or message.get('function_call') or type(message.get('content')) is not str
            or not 1<=len(message['content'])<=16384):raise ValueError('bounded_raw_completion_required')
    usage=value.get('usage')
    if (type(usage) is not dict or not {'prompt_tokens','completion_tokens','total_tokens'}<=set(usage)):
        raise ValueError('actual_usage_required')
    usage={k:usage[k] for k in ('prompt_tokens','completion_tokens','total_tokens')}
    if (any(type(v) is not int or not 0<=v<=10000000 for v in usage.values()) or usage['completion_tokens']>MAX_OUTPUT_TOKENS
            or usage['total_tokens']!=usage['prompt_tokens']+usage['completion_tokens']):raise ValueError('actual_usage_required')
    try:
        authorize();_rules()
        if compact._canonical(prepared)!=binding:raise ValueError('calibration_preparation_changed')
    except Exception as error:
        error.unscored_raw_response=dict(raw_output=message['content'],finish_reason=choice['finish_reason'],usage=usage,reason='post_response_authorization_failed')
        raise
    return dict(raw_output=message['content'],usage=usage,finish_reason=choice['finish_reason'],model=MODEL,origin=ORIGIN,
                model_sampling_seed=SEED,input_sha256=fixed['input_sha256'],model_calls=1,review_required=True,synthetic_only=True)
