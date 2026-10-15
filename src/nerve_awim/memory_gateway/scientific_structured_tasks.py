"""Two fresh structured-output preflight tasks; no efficacy or promotion claim."""
import json

ARMS=('unrestricted_json','schema_json')
_FIELDS=('status','entity','measurement','value','unit','source_id')
_INSTRUCTION=('Use only supplied evidence. Match the requested entity, measurement and exact unit; do not convert units. '
    'If no matching evidence exists or any matching values conflict, abstain. '
    'Return one JSON object only, with status, entity, measurement, value, unit and source_id. '
    'For an answer set status to "answer" and copy the supporting measurement and source_id; '
    'entity must be the bare sample name without the word Sample. All fields are strings. '
    'For abstention set status to "abstain" and set all five other fields to empty strings. '
    'Do not include explanations, code fences or additional keys.')
_SPECS=(
    ('supported_mass',"What is sample Magnolia's mass in mg?",
     (('Sample Sycamore has mass 27.6 mg.','structured-a'),('Sample Magnolia has mass 26.5 mg.','structured-b')),
     ('answer','Magnolia','mass','26.5','mg','structured-b')),
    ('conflicting_mass',"What is sample Buckeye's mass in mg?",
     (('Sample Buckeye has mass 29.2 mg.','structured-c'),('Sample Buckeye has mass 29.7 mg.','structured-d')),
     ('abstain','','','','','')),
)


def _schema():
    return {'type':'object','properties':{'status':{'type':'string','enum':['answer','abstain']},
        **{name:{'type':'string'} for name in _FIELDS if name!='status'}},
        'required':list(_FIELDS),'additionalProperties':False}


def _tasks():
    return {identifier:{'query':query,'evidence':[{'content':content,'source_id':source} for content,source in evidence],
                        'expected':dict(zip(_FIELDS,expected))} for identifier,query,evidence,expected in _SPECS}


TASKS=_tasks()
SCHEMA=_schema()
INSTRUCTION=_INSTRUCTION


def _task(task_id):
    if TASKS!=_tasks() or json.dumps(SCHEMA,sort_keys=True)!=json.dumps(_schema(),sort_keys=True) or INSTRUCTION!=_INSTRUCTION or ARMS!=('unrestricted_json','schema_json'):
        raise ValueError('frozen_structured_registry_changed')
    if type(task_id) is not str or task_id not in TASKS: raise ValueError('unregistered_structured_task')
    return TASKS[task_id]


def trusted_task(task_id):
    return INSTRUCTION+'\n'+_task(task_id)['query']+'\nOutput schema: '+json.dumps(SCHEMA,sort_keys=True,separators=(',',':'))


def _object(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise ValueError('duplicate_json_key')
        result[key]=value
    return result


def _nonfinite(value): raise ValueError('nonfinite_json_constant')


def parse_shape(output):
    """Validate JSON against the generic schema, independently of task rules."""
    if type(output) is not str or not 1<=len(output)<=16384: raise ValueError('invalid_structured_output')
    try: value=json.loads(output,object_pairs_hook=_object,parse_constant=_nonfinite)
    except (ValueError,TypeError,RecursionError) as error: raise ValueError('invalid_structured_output') from error
    if (type(value) is not dict or set(value)!=set(_FIELDS)
            or any(type(value[key]) is not str for key in _FIELDS)
            or value['status'] not in ('answer','abstain')):
        raise ValueError('invalid_structured_output')
    return value


def parse(output):
    """Additionally enforce the empty-field abstention response contract."""
    value=parse_shape(output)
    if value['status']=='abstain' and any(value[key]!='' for key in _FIELDS if key!='status'):
        raise ValueError('invalid_structured_abstention')
    return value


def judge(output,task_id):
    """Unsupported selection concerns a parsed answer on an abstention task only.

    Incorrect fields on a supported task remain strict failures; malformed output
    is a format failure, never evidence of a factually unsupported selection.
    """
    task=_task(task_id)
    try: value=parse_shape(output)
    except ValueError:
        return {'schema_valid':False,'format_valid':False,'strict_correct':False,'unsupported_selection':False}
    if value['status']=='abstain' and any(value[key]!='' for key in _FIELDS if key!='status'):
        return {'schema_valid':True,'format_valid':False,'strict_correct':False,'unsupported_selection':False}
    return {'schema_valid':True,'format_valid':True,'strict_correct':value==task['expected'],
            'unsupported_selection':value['status']=='answer' and task['expected']['status']=='abstain'}
