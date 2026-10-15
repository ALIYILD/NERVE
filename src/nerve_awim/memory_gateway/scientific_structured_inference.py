"""Paired JSON-output experiment: only response_format differs between arms.

Both arms use the same trusted registered contract and question. Evidence remains
untrusted data. All network limits, parsing, retrieval and post-call authority
checks remain those of LocalInferenceAdapter. No feedback or promotion occurs.
"""
import json
from urllib.request import Request

from . import scientific_structured_tasks as tasks
from .inference import LocalInferenceAdapter
from .scientific_model_learning import MODEL, ORIGIN
from .scientific_task_interface import _PARENT_SYSTEM, _SAFETY, _object, _canonical

class _StructuredOpener:
    """One local request rewrite, followed by the original no-proxy opener."""
    def __init__(self, delegate, task_id, constrained):
        self.delegate, self.task_id, self.constrained = delegate, task_id, constrained

    def open(self, request, *, timeout):
        trusted = tasks.trusted_task(self.task_id)
        if (type(request) is not Request or request.full_url != ORIGIN+'/v1/chat/completions'
                or request.get_method() != 'POST' or type(timeout) is not float or timeout != 90.0
                or dict(request.header_items()) != {'Content-type':'application/json','Accept':'application/json'}
                or request.unredirected_hdrs or type(request.data) is not bytes
                or len(request.data) > 1048576):
            raise ValueError('parent_request_contract_changed')
        payload = json.loads(request.data, object_pairs_hook=_object)
        try:
            user = json.loads(payload['messages'][1]['content'], object_pairs_hook=_object)
            if (type(user) is not dict or set(user) != {'query','evidence_jsonl'}
                    or user['query'] != tasks._task(self.task_id)['query'] or type(user['evidence_jsonl']) is not str):
                raise ValueError('unregistered_parent_query')
            expected = {'model':MODEL, 'temperature':0, 'stream':False, 'max_tokens':128,
                'messages':[{'role':'system','content':_PARENT_SYSTEM},
                    {'role':'user','content':json.dumps(user,ensure_ascii=True)}]}
            if _canonical(payload) != _canonical(expected):
                raise ValueError('parent_payload_contract_changed')
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError('parent_payload_contract_changed') from error
        payload['messages'][0]['content'] = _SAFETY + trusted
        if self.constrained:
            payload['response_format'] = {'type':'json_schema','json_schema':{
                'name':'scientific_measurement','strict':True,'schema':tasks.SCHEMA}}
        rewritten = Request(request.full_url, data=json.dumps(payload).encode(),
                            headers=dict(request.header_items()), method=request.get_method())
        return self.delegate.open(rewritten, timeout=timeout)


class StructuredScientificInference(LocalInferenceAdapter):
    """Host-selected registered task and explicit decoder constraint flag."""
    def __init__(self, task_id, constrained: bool):
        if type(constrained) is not bool:
            raise ValueError('explicit_boolean_constraint_required')
        tasks.trusted_task(task_id)
        self.task_id, self.constrained = task_id, constrained
        super().__init__(base_url=ORIGIN,model=MODEL,max_output_tokens=128,
                         timeout_seconds=90,runtime_profile='cpu_research')
        self._opener = _StructuredOpener(self._opener,task_id,constrained)

    def _model_response(self, query, context):
        if type(query) is not str or query != tasks._task(self.task_id)['query']:
            raise ValueError('registered_task_query_required')
        return super()._model_response(query,context)
