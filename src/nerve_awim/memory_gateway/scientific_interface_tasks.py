"""Fresh development tasks for a trusted-task versus JSON-task interface study.

Both arms use the same fixed direct instruction and evidence. Answer keys remain
host evaluator data; trusted_task returns instructions and the question only.
"""
import re
from . import scientific_measurement_tasks as original

_TASKS = (
    ('measurement_decoy',"What is sample Linden's mass in mg?",
     (('Sample Linden has mass 18.7 mg.','interface-a'),('Sample Linden has temperature 24.3 C.','interface-b')),
     'Linden|mass|18.7|mg|interface-a'),
    ('entity_decoy',"What is sample Maple's volume in mL?",
     (('Sample Juniper has volume 9.6 mL.','interface-c'),('Sample Maple has volume 3.8 mL.','interface-d')),
     'Maple|volume|3.8|mL|interface-d'),
    ('unit_mismatch',"What is sample Rowan's mass in mg?",
     (('Sample Rowan has mass 0.6 g.','interface-e'),('Sample Willow has mass 8.3 mg.','interface-f')),
     'ABSTAIN'),
    ('conflict',"What is sample Hazel's mass in mg?",
     (('Sample Hazel has mass 11.2 mg.','interface-g'),('Sample Hazel has mass 11.9 mg.','interface-h')),
     'ABSTAIN'),
)
DIRECT_PREFIX = original.STRATEGIES['direct']
_REGISTERED_PREFIX = DIRECT_PREFIX
ARMS = ('baseline_json','trusted_task')
# Retain the exact original output grammar, without modifying its source.
_TUPLE = re.compile(original._TUPLE.pattern,original._TUPLE.flags)


def _tasks():
    return {identifier:{'query':query,'evidence':[{'content':content,'source_id':source} for content,source in evidence],
                        'expected':expected} for identifier,query,evidence,expected in _TASKS}


TASKS = _tasks()


def _task(task_id):
    if TASKS != _tasks() or DIRECT_PREFIX != _REGISTERED_PREFIX or original.STRATEGIES['direct'] != _REGISTERED_PREFIX:
        raise ValueError('frozen_interface_registry_changed')
    if type(task_id) is not str or task_id not in TASKS: raise ValueError('unregistered_interface_task')
    return TASKS[task_id]


def trusted_task(task_id):
    """Host-only registered instruction, never arbitrary caller instructions."""
    return DIRECT_PREFIX+'\n'+_task(task_id)['query']


def judge(output,task_id):
    """Score raw output exactly; formatting failure is not factual disproof."""
    task=_task(task_id)
    if type(output) is not str:
        return {'strict_correct':False,'format_failure':True,'non_abstaining_contract_failure':False}
    value=output.strip();correct=value==task['expected']
    return {'strict_correct':correct,
        'format_failure':not(value=='ABSTAIN' or _TUPLE.fullmatch(value) is not None),
        'non_abstaining_contract_failure':bool(value) and value!='ABSTAIN' and not correct}
