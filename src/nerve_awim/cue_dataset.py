"""Strict local frozen benchmark inputs for existing CCE experiments.

JSON schema (all keys required; additional and duplicate keys rejected)::

    {"schema_version": 1, "dataset_id": "fixture-v1",
     "source": {"uri": "fixture:local", "revision": "commit-or-release"},
     "splits": {
       "discovery": [{"task_id": "d1", "family_id": "family-d",
                      "instruction": "Problem", "expected": "Answer"}],
       "selection": [...], "holdout": [...]}}

``load_dataset(path)`` reads a bounded regular local UTF-8 JSON file;
``parse_dataset_json(raw)`` applies the same schema to bytes or text. The result
exposes existing DatasetManifest and ExperimentTask tuples. Pass ONLY .manifest
to discovery adapters; expected answers remain host-side for independent judges.
The loader never downloads evidence, invokes an agent, or verifies a publisher's
revision claim. Family labels are host annotations, not semantic deduplication.
"""
from dataclasses import dataclass, field
from hashlib import sha256
import json
import os
import re
import stat

from .cue_evaluation import DatasetManifest
from .cue_experiment import ExperimentTask

MAX_DATASET_BYTES = 4 * 1024 * 1024
MAX_DATASET_TASKS = 10000
_SPLITS = ('discovery', 'selection', 'holdout')
_IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:/@+\-]{0,127}\Z')


def _identifier(value):
    if type(value) is not str or not _IDENTIFIER.fullmatch(value):
        raise ValueError('bounded ASCII dataset, task and family identifiers required')


def _text(value, *, limit):
    if type(value) is not str or not value.strip():
        raise ValueError('nonempty bounded dataset text required')
    try:
        encoded = value.encode('utf-8')
    except UnicodeError:
        raise ValueError('valid UTF-8 dataset text required') from None
    if len(encoded) > limit or any(ord(c) < 32 and c not in '\n\r\t' for c in value):
        raise ValueError('invalid or excessive dataset text')


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate dataset JSON key')
        result[key] = value
    return result


def _constant(value):
    raise ValueError('nonfinite dataset JSON value')


def _keys(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        raise ValueError('strict dataset JSON schema required')


def _limits(max_bytes, max_tasks):
    if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_DATASET_BYTES:
        raise ValueError('bounded dataset byte cap required')
    if type(max_tasks) is not int or not 3 <= max_tasks <= MAX_DATASET_TASKS:
        raise ValueError('bounded dataset task cap required')


@dataclass(frozen=True)
class FrozenCueDataset:
    dataset_id: str
    source_uri: str
    source_revision: str
    digest: str
    manifest: DatasetManifest
    discovery_tasks: tuple = field(repr=False)
    selection_tasks: tuple = field(repr=False)
    holdout_tasks: tuple = field(repr=False)
    families: tuple = field(repr=False)

    def telemetry(self):
        """Counts and identity only; no source text, questions or expected answers."""
        return {'dataset_id': self.dataset_id, 'digest': self.digest,
                'schema_version': 1,
                'counts': {split: len(getattr(self.manifest, split)) for split in _SPLITS}}


def parse_dataset_json(raw, *, max_bytes=MAX_DATASET_BYTES, max_tasks=MAX_DATASET_TASKS):
    """Validate and freeze UTF-8 JSON; formatting/key order do not affect digest.

    Task order IS significant: experiments alternate arm ordering by task index.
    Instructions and expected answers retain exact original whitespace. Duplicate
    instructions are rejected using stripped text, matching run_experiment's
    guard; semantically related paraphrases additionally require family labels.
    """
    _limits(max_bytes, max_tasks)
    if type(raw) not in (str, bytes):
        raise TypeError('JSON text or UTF-8 bytes required')
    try:
        if type(raw) is str:
            if len(raw) > max_bytes:
                raise ValueError('dataset exceeds byte cap')
            encoded = raw.encode('utf-8')
        else:
            encoded = raw
        if len(encoded) > max_bytes:
            raise ValueError('dataset exceeds byte cap')
        text = encoded.decode('utf-8')
        record = json.loads(text, object_pairs_hook=_object, parse_constant=_constant)
    except (UnicodeError, RecursionError, json.JSONDecodeError):
        raise ValueError('valid bounded UTF-8 dataset JSON required') from None
    _keys(record, ('schema_version', 'dataset_id', 'source', 'splits'))
    if type(record['schema_version']) is not int or record['schema_version'] != 1:
        raise ValueError('dataset schema version 1 required')
    _identifier(record['dataset_id'])
    _keys(record['source'], ('uri', 'revision'))
    for name in ('uri', 'revision'):
        _text(record['source'][name], limit=2048 if name == 'uri' else 256)
        if any(c.isspace() for c in record['source'][name]):
            raise ValueError('source URI and revision must be explicit single identifiers')
    _keys(record['splits'], _SPLITS)
    count = 0
    for split in _SPLITS:
        tasks = record['splits'][split]
        if type(tasks) is not list or not tasks:
            raise ValueError('all dataset splits require nonempty task arrays')
        count += len(tasks)
        if count > max_tasks:
            raise ValueError('dataset exceeds task cap')
    seen_ids, seen_instructions, family_splits = set(), set(), {}
    frozen, families = {}, []
    for split in _SPLITS:
        tasks = []
        for task in record['splits'][split]:
            _keys(task, ('task_id', 'family_id', 'instruction', 'expected'))
            _identifier(task['task_id']); _identifier(task['family_id'])
            _text(task['instruction'], limit=65536)
            _text(task['expected'], limit=65536)
            if task['task_id'] in seen_ids:
                raise ValueError('duplicate task ID across dataset')
            seen_ids.add(task['task_id'])
            fingerprint = sha256(task['instruction'].strip().encode()).hexdigest()
            if fingerprint in seen_instructions:
                raise ValueError('duplicate instruction content across dataset')
            seen_instructions.add(fingerprint)
            family = task['family_id']
            if family in family_splits and family_splits[family] != split:
                raise ValueError('task family crosses dataset splits')
            family_splits[family] = split
            families.append((task['task_id'], family, split))
            tasks.append(ExperimentTask(task['task_id'], task['instruction'], task['expected']))
        frozen[split] = tuple(tasks)
    manifest = DatasetManifest(*(tuple(task.task_id for task in frozen[split]) for split in _SPLITS))
    digest = sha256(json.dumps(record, sort_keys=True, separators=(',', ':'),
                              ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    return FrozenCueDataset(record['dataset_id'], record['source']['uri'], record['source']['revision'],
                            digest, manifest, *(frozen[split] for split in _SPLITS), tuple(families))


def load_dataset(path, *, max_bytes=MAX_DATASET_BYTES, max_tasks=MAX_DATASET_TASKS):
    """Read at most max_bytes+1 bytes, refusing devices/directories/FIFOs.

    No environment expansion, URL resolution, network access or working-directory
    changes occur. Nonblocking open prevents waiting on a FIFO masquerading as a
    dataset; fstat checks the opened handle rather than a race-prone path check.
    """
    _limits(max_bytes, max_tasks)
    fd = os.open(os.fspath(path), os.O_RDONLY | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as handle:
        metadata = os.fstat(handle.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError('regular local dataset file required')
        if metadata.st_size > max_bytes:
            raise ValueError('dataset exceeds byte cap')
        raw = handle.read(max_bytes + 1)
    return parse_dataset_json(raw, max_bytes=max_bytes, max_tasks=max_tasks)
