#!/usr/bin/env python3
"""CPU-only public protocol fixtures; never generates or opens bank-v3 data."""
from copy import deepcopy
from pathlib import Path
import json
from nerve_awim.memory_gateway import scientific_candidate_v3 as candidate
from nerve_awim.memory_gateway import scientific_task_bank as bank


def check():
    sample = bank._item(bytes(32), 'dev', 'supported-measurement', 0)
    expected = sample['expected']
    original = sample['evidence'][0]
    cases = [
        ('familyB', f"Mass of sample {expected['entity']}: {expected['value']} mg (current)."),
        ('qualified_measurement', f"Sample {expected['entity']} has dry mass {expected['value']} mg."),
    ]
    outputs = []
    for name, text in cases:
        record = deepcopy(original)
        record['content'] = text
        record['content_sha256'] = bank._hash({k: v for k, v in record.items() if k != 'content_sha256'})
        for arm in ('candidate', 'baseline'):
            try:
                prepared = candidate.prepare(sample['query'], [record], arm=arm)
                result = {k: prepared[k] for k in ('route', 'gate_reason')}
            except ValueError as error:
                result = {'error': str(error)}
            outputs.append({'case': name, 'arm': arm, 'result': result})
    assert all(row['result'] == ({'route': 'deterministic_abstention', 'gate_reason': 'unsupported_evidence'}
               if row['arm'] == 'candidate' else {'error': 'supported_baseline_input_required'}) for row in outputs)
    return {'scope': 'CPU-only synthetic protocol compatibility fixtures; not bank-v3 items or efficacy study',
            'model_calls': 0, 'results': outputs,
            'finding': 'Family B and qualified measurements are outside frozen compact grammar; bootstrap baseline raises before model call. Numeric conflict comparison already Decimal.'}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
