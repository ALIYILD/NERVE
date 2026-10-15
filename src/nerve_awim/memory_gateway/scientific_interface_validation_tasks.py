"""Fresh balanced validation tasks for the unchanged registered task interface.

Only query and evidence enter prompts. Host answer keys and stratum labels do
not. The prompt prefix, output grammar and scoring semantics remain unchanged.
"""
import re
from . import scientific_interface_tasks as previous

DIRECT_PREFIX=previous.DIRECT_PREFIX
_REGISTERED_PREFIX=DIRECT_PREFIX
ARMS=('baseline_json','trusted_task')
_TUPLE=re.compile(previous._TUPLE.pattern,previous._TUPLE.flags)
_SPECS=(
    ('measurement_mass','measurement_decoy',"What is sample Acacia's mass in mg?",
     (('Sample Acacia has mass 16.8 mg.','validation-a'),('Sample Acacia has volume 2.7 mL.','validation-b')),
     'Acacia|mass|16.8|mg|validation-a'),
    ('measurement_volume','measurement_decoy',"What is sample Spruce's volume in mL?",
     (('Sample Spruce has mass 13.6 mg.','validation-c'),('Sample Spruce has volume 6.4 mL.','validation-d')),
     'Spruce|volume|6.4|mL|validation-d'),
    ('entity_mass','entity_decoy',"What is sample Cypress's mass in mg?",
     (('Sample Sequoia has mass 17.1 mg.','validation-e'),('Sample Cypress has mass 10.6 mg.','validation-f')),
     'Cypress|mass|10.6|mg|validation-f'),
    ('entity_volume','entity_decoy',"What is sample Aspen's volume in mL?",
     (('Sample Aspen has volume 14.8 mL.','validation-g'),('Sample Hemlock has volume 19.3 mL.','validation-h')),
     'Aspen|volume|14.8|mL|validation-g'),
    ('unit_mass','unit_mismatch',"What is sample Tamarack's mass in mg?",
     (('Sample Tamarack has mass 0.9 g.','validation-i'),('Sample Chestnut has mass 15.7 mg.','validation-j')),
     'ABSTAIN'),
    ('unit_volume','unit_mismatch',"What is sample Dogwood's volume in mL?",
     (('Sample Beech has volume 22.8 mL.','validation-k'),('Sample Dogwood has volume 1.4 L.','validation-l')),
     'ABSTAIN'),
    ('conflict_mass','conflict',"What is sample Poplar's mass in mg?",
     (('Sample Poplar has mass 20.1 mg.','validation-m'),('Sample Poplar has mass 20.9 mg.','validation-n')),
     'ABSTAIN'),
    ('conflict_volume','conflict',"What is sample Alder's volume in mL?",
     (('Sample Alder has volume 23.4 mL.','validation-o'),('Sample Alder has volume 23.8 mL.','validation-p')),
     'ABSTAIN'),
)


def _tasks():
    return {identifier:{'query':query,'evidence':[{'content':content,'source_id':source} for content,source in evidence],
                        'expected':expected} for identifier,stratum,query,evidence,expected in _SPECS}


TASKS=_tasks()
STRATA={identifier:stratum for identifier,stratum,query,evidence,expected in _SPECS}


def _task(task_id):
    if (TASKS!=_tasks() or STRATA!={row[0]:row[1] for row in _SPECS}
            or DIRECT_PREFIX!=_REGISTERED_PREFIX or previous.DIRECT_PREFIX!=_REGISTERED_PREFIX):
        raise ValueError('frozen_interface_validation_registry_changed')
    if type(task_id) is not str or task_id not in TASKS:
        raise ValueError('unregistered_interface_validation_task')
    return TASKS[task_id]


def trusted_task(task_id):
    return DIRECT_PREFIX+'\n'+_task(task_id)['query']


def judge(output,task_id):
    """Exact raw contract; a format failure does not disprove factual content."""
    task=_task(task_id)
    if type(output) is not str:
        return {'strict_correct':False,'format_failure':True,'non_abstaining_contract_failure':False}
    value=output.strip();correct=value==task['expected']
    return {'strict_correct':correct,
            'format_failure':not(value=='ABSTAIN' or _TUPLE.fullmatch(value) is not None),
            'non_abstaining_contract_failure':bool(value) and value!='ABSTAIN' and not correct}
