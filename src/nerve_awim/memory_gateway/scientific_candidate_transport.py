"""Fixed-loopback transport for bounded candidate execution; no model promotion."""
import json
from threading import BoundedSemaphore, Lock
from urllib.request import Request

from . import scientific_candidate_execution as execution
from .inference import LocalInferenceAdapter, InferenceUnavailable
from .scientific_model_learning import MODEL, ORIGIN
from .scientific_task_interface import _PARENT_SYSTEM, _object, _canonical


class _Opener:
    def __init__(self,delegate,adapter):self.delegate,self.adapter=delegate,adapter

    def open(self,request,*,timeout):
        binding=self.adapter._binding
        if binding is None:raise ValueError('unbound_candidate_request')
        prepared,constrained=json.loads(binding)
        context='\n'.join(_canonical(record) for record in prepared['evidence'])
        expected={'model':MODEL,'temperature':0,'stream':False,'max_tokens':128,'messages':[
            {'role':'system','content':_PARENT_SYSTEM},
            {'role':'user','content':json.dumps({'query':prepared['query'],'evidence_jsonl':context},ensure_ascii=True)}]}
        if (type(request) is not Request or request.full_url!=ORIGIN+'/v1/chat/completions'
                or request.get_method()!='POST' or type(timeout) is not float or timeout!=90.0
                or dict(request.header_items())!={'Content-type':'application/json','Accept':'application/json'}
                or request.unredirected_hdrs or type(request.data) is not bytes or len(request.data)>1048576
                or _canonical(json.loads(request.data,object_pairs_hook=_object))!=_canonical(expected)):
            raise ValueError('parent_request_contract_changed')
        expected['messages'][0]['content']=prepared['system']
        if constrained:
            expected['response_format']={'type':'json_schema','json_schema':{
                'name':'scientific_measurement','strict':True,'schema':execution.SCHEMA}}
        rewritten=Request(request.full_url,data=json.dumps(expected).encode(),method='POST',headers=dict(request.header_items()))
        return self.delegate.open(rewritten,timeout=timeout)


class _LocalTransport(LocalInferenceAdapter):
    def __init__(self):
        super().__init__(base_url=ORIGIN,model=MODEL,max_output_tokens=128,timeout_seconds=90,runtime_profile='cpu_research')
        self._call_slot=BoundedSemaphore(1);self._binding=None
        self._opener=_Opener(self._opener,self)

    def invoke(self,payload,constrained):
        if type(payload) is not dict or set(payload)!={'system','query','evidence'} or type(constrained) is not bool:
            raise ValueError('prepared_candidate_payload_required')
        if not self._call_slot.acquire(blocking=False):raise InferenceUnavailable('capacity')
        try:
            self._binding=_canonical([payload,constrained])
            context='\n'.join(_canonical(record) for record in payload['evidence'])
            output,usage=super()._model_response(payload['query'],context)
            if (set(usage)!={'prompt_tokens','completion_tokens','total_tokens'}
                    or usage['total_tokens']!=usage['prompt_tokens']+usage['completion_tokens']):
                raise ValueError('actual_complete_usage_required')
            if self._binding!=_canonical([payload,constrained]):raise ValueError('candidate_binding_changed')
            return output,usage
        finally:
            self._binding=None;self._call_slot.release()


_INSTANCE=None
_INSTANCE_LOCK=Lock()


def _transport():
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:_INSTANCE=_LocalTransport()
        return _INSTANCE


def run(config,query,evidence,*,authorize,constrained=False):
    """Caller supplies authoritative identity/source revalidation; no retries.

    Metadata/digest verification belongs to the pre-registered host study. This
    function reports the fixed model name, never invents a verified digest.
    """
    if type(constrained) is not bool:raise ValueError('boolean_constraint_required')
    # Compile expected callback content independently, before dispatch. execute
    # also snapshots and validates inputs/rules across authorization callbacks.
    prepared=execution.prepare(config,query,evidence)
    expected=_canonical({k:prepared[k] for k in ('system','query','evidence')})
    usage=None
    def model(payload):
        nonlocal usage
        if _canonical(payload)!=expected:raise ValueError('unexpected_candidate_payload')
        output,usage=_transport().invoke(payload,constrained)
        return output
    result=execution.execute(config,query,evidence,model,authorize=authorize)
    return dict(**result,usage=usage,model=MODEL,origin=ORIGIN,constrained=constrained)
