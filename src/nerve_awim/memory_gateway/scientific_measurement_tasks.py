"""Frozen development tasks for raw measurement/entity/unit/source binding.

Answer keys remain host evaluator data. Only query, evidence and a registered
strategy prefix belong in model inputs. This is extraction, not discovery.
"""
import re

_TASKS = (
    ('measurement_decoy',"What is sample Aster's mass in mg?",
     (('Sample Aster has mass 12.4 mg.','obs-a'),('Sample Aster has temperature 21.6 C.','obs-b')),
     'Aster|mass|12.4|mg|obs-a'),
    ('entity_decoy',"What is sample Beryl's volume in mL?",
     (('Sample Cedar has volume 4.2 mL.','obs-c'),('Sample Beryl has volume 7.5 mL.','obs-d')),
     'Beryl|volume|7.5|mL|obs-d'),
    ('unit_mismatch',"What is sample Flint's mass in mg?",
     (('Sample Flint has mass 0.8 g.','obs-e'),('Sample Garnet has mass 6.1 mg.','obs-f')),
     'ABSTAIN'),
    ('conflict',"What is sample Iris's mass in mg?",
     (('Sample Iris has mass 5.2 mg.','obs-g'),('Sample Iris has mass 5.8 mg.','obs-h')),
     'ABSTAIN'),
)
_COMMON = ('Use only supplied evidence. Match the requested entity, measurement and exact unit. '
    'Do not convert units. If no matching evidence exists or matching values conflict, output ABSTAIN. '
    'Otherwise output exactly entity|measurement|value|unit|source_id using the supporting source. '
    'Output one line only, without explanations or code fences. ')
_STRATEGIES = (
    ('direct',_COMMON+'Answer the question directly.'),
    ('checklist',_COMMON+'Before answering, check the entity, measurement, unit, conflicting values and supporting source_id. Do not print the checklist.'),
)


def _tasks():
    return {identifier:{'query':query,'evidence':[{'content':content,'source_id':source} for content,source in evidence],
                        'expected':expected} for identifier,query,evidence,expected in _TASKS}


TASKS = _tasks()
STRATEGIES = dict(_STRATEGIES)
EVALUATOR_REVISION = 'scientific-measurement-exact-v1'
_TUPLE = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,31}\|(?:mass|volume|temperature)\|(?:0|[1-9][0-9]{0,5})(?:\.[0-9]{1,4})?\|(?:mg|g|mL|L|C)\|[A-Za-z0-9_.:-]{1,96}')


def _task(task_id):
    if TASKS != _tasks() or STRATEGIES != dict(_STRATEGIES):
        raise ValueError('frozen_measurement_registry_changed')
    if type(task_id) is not str or task_id not in TASKS:
        raise ValueError('unregistered_measurement_task')
    return TASKS[task_id]


def judge(output,task_id):
    """Exact raw scoring; no repairs, fuzzy extraction or deterministic answers.

    A non-abstaining contract failure can contain a factually correct answer in
    the wrong format. It is not a semantic unsupported-answer classification.
    """
    task = _task(task_id)
    if type(output) is not str:
        return {'strict_correct':False,'format_failure':True,'non_abstaining_contract_failure':False}
    value = output.strip()
    formatted = value=='ABSTAIN' or _TUPLE.fullmatch(value) is not None
    correct = value==task['expected']
    # Count nonempty non-abstentions failing the exact contract, including
    # formatting failures. This does not establish factual unsupportedness.
    contract_failure = bool(value) and value!='ABSTAIN' and not correct
    return {'strict_correct':correct,'format_failure':not formatted,'non_abstaining_contract_failure':contract_failure}


def evaluate(record,task,output):
    """Trusted-host evaluator for existing VerifiedOutcomeLearning.

    Strategy ID belongs in task identity so matched arms do not collide in the
    existing ranker's replay ledger. No caller-supplied answer key is accepted.
    """
    if type(task) is not dict or set(task)!={'task_id','strategy_id'}:
        return False
    strategy = task['strategy_id']
    if (type(strategy) is not str or strategy not in STRATEGIES
            or type(getattr(record,'content',None)) is not str or record.content!=strategy):
        return False
    try: return judge(output,task['task_id'])['strict_correct']
    except ValueError: return False
