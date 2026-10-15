"""Compact synthetic evidence interface with reversible aliases and measured token cap.

The 150-token cap covers runtime-reported total prompt tokens, checked after the
single call. No tokenizer preflight guarantee is claimed. No answer keys enter
this transport, and decoding never repairs output values or syntax.
"""
import json
import re
from threading import BoundedSemaphore, Lock
from urllib.request import Request

from . import scientific_candidate_execution as grammar
from .inference import LocalInferenceAdapter, InferenceUnavailable
from .scientific_model_learning import MODEL, ORIGIN
from .scientific_task_interface import _PARENT_SYSTEM, _canonical, _object

SYSTEM='Use only facts. Return value|unit|source for the queried entity/measurement/unit, or ABSTAIN if absent/conflicting. No unit conversion or prose.'
MAX_PROMPT_TOKENS=150
MAX_OUTPUT_TOKENS=32
SEED=20261015

_FROZEN_POLICY=_canonical([SYSTEM,MAX_PROMPT_TOKENS,MAX_OUTPUT_TOKENS,MODEL,ORIGIN,SEED])
_GRAMMAR_RULE_GUARD=grammar._rules


def _policy():
    if _canonical([SYSTEM,MAX_PROMPT_TOKENS,MAX_OUTPUT_TOKENS,MODEL,ORIGIN,SEED])!=_FROZEN_POLICY:
        raise ValueError('compact_transport_policy_changed')
    _GRAMMAR_RULE_GUARD()


class PromptBudgetExceeded(ValueError):
    def __init__(self,raw_output,usage):
        super().__init__('runtime_prompt_token_budget_exceeded')
        self.raw_output=raw_output
        self.usage=dict(usage)
        self.prompt_limit=MAX_PROMPT_TOKENS


def prepare(query,evidence):
    _policy()
    grammar._inputs(query,evidence)
    requested=grammar.QUERY.fullmatch(query)
    if requested is None:raise ValueError('registered_compact_query_required')
    target=requested.group(1)
    parsed=[]
    for record in evidence:
        match=grammar.FACT.fullmatch(record['content'])
        if match is None:raise ValueError('registered_compact_fact_required')
        if not record['current']:raise ValueError('current_compact_evidence_required')
        parsed.append((record,match.groups()))
    if not 1<=len(parsed)<=8:raise ValueError('bounded_compact_facts_required')
    entities=[target]+sorted({parts[0] for _,parts in parsed}-{target})
    entity_aliases={entity:'E'+str(i) for i,entity in enumerate(entities)}
    aliases={};facts=[]
    for index,(record,parts) in enumerate(sorted(parsed,key=lambda row:row[0]['source_id'])):
        entity,measurement,value,unit=parts;alias='A'+str(index)
        aliases[alias]=dict(source_id=record['source_id'],entity=entity,measurement=measurement,value=value,unit=unit)
        facts.append(f'{alias} {entity_aliases[entity]} {measurement} {value} {unit}')
    body=dict(query=query,evidence=json.loads(_canonical(evidence)),system=SYSTEM,
        user='Query: E0 mass mg\nFacts: '+'; '.join(facts),aliases=aliases,
        entity_aliases=entity_aliases,input_sha256=grammar.candidates._hash({'query':query,'evidence':evidence}))
    return json.loads(_canonical(body))


def _checked(prepared):
    if type(prepared) is not dict:raise ValueError('prepared_compact_request_required')
    try:expected=prepare(prepared['query'],prepared['evidence'])
    except (KeyError,TypeError) as error:raise ValueError('prepared_compact_request_required') from error
    if _canonical(prepared)!=_canonical(expected):raise ValueError('compact_preparation_changed')
    return expected


def decode(raw,prepared):
    fixed=_checked(prepared)
    if type(raw) is not str or not 1<=len(raw)<=16384:raise ValueError('bounded_raw_output_required')
    value=raw.strip()
    if value=='ABSTAIN':return dict(grammar.ABSTAIN)
    match=re.fullmatch(r'([0-9]{1,12}(?:\.[0-9]{1,12})?)\|(mg|g|mL|L|C)\|(A[0-7])',value)
    if match is None or match.group(3) not in fixed['aliases']:raise ValueError('strict_compact_output_required')
    amount,unit,alias=match.groups();source=fixed['aliases'][alias]
    return dict(status='answer',entity=source['entity'],measurement=source['measurement'],
                value=amount,unit=unit,source_id=source['source_id'])


class _Opener:
    def __init__(self,delegate,adapter):self.delegate,self.adapter=delegate,adapter
    def open(self,request,*,timeout):
        _policy()
        if self.adapter._binding is None:raise ValueError('unbound_compact_request')
        prepared=json.loads(self.adapter._binding)
        expected={'model':MODEL,'temperature':0,'stream':False,'max_tokens':MAX_OUTPUT_TOKENS,'messages':[
            {'role':'system','content':_PARENT_SYSTEM},
            {'role':'user','content':json.dumps({'query':prepared['user'],'evidence_jsonl':''},ensure_ascii=True)}]}
        if (type(request) is not Request or request.full_url!=ORIGIN+'/v1/chat/completions'
                or request.get_method()!='POST' or type(timeout) is not float or timeout!=90.0
                or dict(request.header_items())!={'Content-type':'application/json','Accept':'application/json'}
                or request.unredirected_hdrs or type(request.data) is not bytes or len(request.data)>1048576
                or _canonical(json.loads(request.data,object_pairs_hook=_object))!=_canonical(expected)):
            raise ValueError('parent_request_contract_changed')
        expected['seed']=SEED
        expected['messages']=[{'role':'system','content':prepared['system']},{'role':'user','content':prepared['user']}]
        rewritten=Request(request.full_url,data=json.dumps(expected).encode(),method='POST',headers=dict(request.header_items()))
        return self.delegate.open(rewritten,timeout=timeout)


class _LocalTransport(LocalInferenceAdapter):
    def __init__(self):
        super().__init__(base_url=ORIGIN,model=MODEL,max_output_tokens=MAX_OUTPUT_TOKENS,timeout_seconds=90,runtime_profile='cpu_research')
        self._call_slot=BoundedSemaphore(1);self._binding=None
        self._opener=_Opener(self._opener,self)
    def invoke(self,prepared):
        checked=_checked(prepared)
        if not self._call_slot.acquire(blocking=False):raise InferenceUnavailable('capacity')
        try:
            self._binding=_canonical(checked)
            raw,usage=super()._model_response(checked['user'],'')
            _policy()
            if (set(usage)!={'prompt_tokens','completion_tokens','total_tokens'}
                    or usage['total_tokens']!=usage['prompt_tokens']+usage['completion_tokens']):
                raise ValueError('actual_complete_usage_required')
            return raw,usage
        finally:self._binding=None;self._call_slot.release()


_INSTANCE=None
_LOCK=Lock()


def _transport():
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:_INSTANCE=_LocalTransport()
        return _INSTANCE


def run(prepared,*,authorize):
    """One call, authorization before/after, measured total prompt cap, no retry."""
    if not callable(authorize):raise ValueError('trusted_host_authorizer_required')
    fixed=_checked(prepared);binding=_canonical(prepared)
    authorize()
    _policy()
    if _canonical(prepared)!=binding:raise ValueError('compact_preparation_changed')
    raw,usage=_transport().invoke(fixed)
    authorize()
    _policy()
    if _canonical(prepared)!=binding:raise ValueError('compact_preparation_changed')
    if usage['prompt_tokens']>MAX_PROMPT_TOKENS:raise PromptBudgetExceeded(raw,usage)
    return dict(raw_output=raw,usage=usage,model=MODEL,origin=ORIGIN,model_calls=1,
        input_sha256=fixed['input_sha256'],model_sampling_seed=SEED,prompt_limit_verified=True,
        prompt_limit_verification='runtime_usage_after_call',max_prompt_tokens=MAX_PROMPT_TOKENS,
        review_required=True,synthetic_only=True,model_weights_trained=False)
