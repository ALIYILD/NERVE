"""Strict local replay input; declared provenance is not independent attestation."""
from copy import deepcopy
from hashlib import sha256
import json
import math
from pathlib import Path


def validate(value):
    value = deepcopy(value)
    if type(value) is not dict or set(value) != {'schema', 'goal_id', 'domain', 'scope', 'provenance', 'target', 'phases'}:
        raise ValueError('exact workload manifest required')
    if value['schema'] != 'nerve-adaptation-workload-v1' or value['domain'] not in ('clinical_os', 'perfflux'):
        raise ValueError('unsupported workload schema or domain')
    def text(v, maximum=128):
        if type(v) is not str or not 1 <= len(v) <= maximum:
            raise ValueError('bounded nonempty text required')
    for field in ('goal_id', 'scope'):
        text(value[field])
    provenance = value['provenance']
    if type(provenance) is not dict or set(provenance) != {'source_ref', 'labeler_ref', 'data_kind'}:
        raise ValueError('source and label provenance required')
    for field in ('source_ref', 'labeler_ref'):
        text(provenance[field], 512)
    allowed = ('synthetic', 'public_nonpatient') if value['domain'] == 'clinical_os' else ('synthetic', 'local_cpu')
    if provenance['data_kind'] not in allowed:
        raise ValueError('only offline nonpatient or CPU workloads supported')
    target = value['target']
    if type(target) is not dict or set(target) != {'min_gain', 'min_monitor_accuracy', 'min_switches', 'max_evaluation_calls'}:
        raise ValueError('exact measurable target required')
    for name, low, high in (('min_gain', .01, 1), ('min_monitor_accuracy', .75, 1)):
        number = target[name]
        if type(number) not in (int, float) or not math.isfinite(number) or not low <= number <= high:
            raise ValueError('invalid target: '+name)
    for name, low, high in (('min_switches', 1, 4), ('max_evaluation_calls', 0, 64)):
        if type(target[name]) is not int or not low <= target[name] <= high:
            raise ValueError('invalid target: '+name)
    if type(value['phases']) is not list or not 2 <= len(value['phases']) <= 4:
        raise ValueError('two to four chronological phases required')
    ids, payloads = set(), set()
    for phase in value['phases']:
        if type(phase) is not dict or set(phase) != {'observe', 'selection', 'retained', 'monitor'}:
            raise ValueError('exact phase partitions required')
        for split, count in (('observe', 4), ('selection', 4), ('retained', 4), ('monitor', 8)):
            if type(phase[split]) is not list or len(phase[split]) != count:
                raise ValueError('incorrect bounded partition size')
            for episode in phase[split]:
                if type(episode) is not dict or set(episode) != {'id', 'task', 'expected'}:
                    raise ValueError('exact labeled episode required')
                text(episode['id'])
                task, expected = episode['task'], episode['expected']
                encoded = json.dumps(task, sort_keys=True, allow_nan=False)
                if episode['id'] in ids or encoded in payloads or len(encoded.encode()) > 16384:
                    raise ValueError('duplicate or oversized task across partitions')
                ids.add(episode['id'])
                payloads.add(encoded)
                if value['domain'] == 'clinical_os':
                    if type(task) is not dict or set(task) != {'query', 'documents'}:
                        raise ValueError('research retrieval task required')
                    text(task['query'], 1024)
                    if type(task['documents']) is not list or not 2 <= len(task['documents']) <= 8:
                        raise ValueError('bounded candidate documents required')
                    documents = set()
                    for doc in task['documents']:
                        if type(doc) is not dict or set(doc) != {'id', 'title', 'abstract'}:
                            raise ValueError('exact research metadata required')
                        for field in doc:
                            text(doc[field], 2048 if field == 'abstract' else 512)
                        if doc['id'] in documents:
                            raise ValueError('duplicate document identity')
                        documents.add(doc['id'])
                    if type(expected) is not dict or set(expected) != {'document'} or expected['document'] not in documents:
                        raise ValueError('independently labeled candidate reference required')
                else:
                    if type(task) is not dict or set(task) != {'payloads', 'call_limit', 'cache_limit'}:
                        raise ValueError('exact CPU batch task required')
                    if type(task['payloads']) is not list or not 1 <= len(task['payloads']) <= 64:
                        raise ValueError('bounded CPU payloads required')
                    for payload in task['payloads']:
                        text(payload, 1024)
                    for field in ('call_limit', 'cache_limit'):
                        if type(task[field]) is not int or not 0 <= task[field] <= 64:
                            raise ValueError('bounded resource limits required')
                    correct = {'digests': [sha256(p.encode()).hexdigest() for p in task['payloads']]}
                    if expected != correct:
                        raise ValueError('CPU correctness labels disagree with independent digest')
    encoded = json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':'))
    if len(encoded.encode()) > 1_000_000:
        raise ValueError('workload byte budget exceeded')
    return value, sha256(encoded.encode()).hexdigest()


def load(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(1_000_001)
    if len(raw) > 1_000_000:
        raise ValueError('workload byte budget exceeded')
    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = item
        return result
    return validate(json.loads(raw, object_pairs_hook=unique))[0]
