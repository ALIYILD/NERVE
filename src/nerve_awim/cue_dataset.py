"""Strict local frozen benchmark inputs for existing CCE experiments.

JSON schema (all keys required; additional and duplicate keys rejected)::

    {"schema_version": 1, "dataset_id": "fixture-v1",
     "source": {"uri": "fixture:local", "revision": "commit-or-release"},
     "splits": {
       "discovery": [{"task_id": "d1", "family_id": "family-d",
                      "instruction": "Problem", "expected": "Answer"}],
       "selection": [...], "holdout": [...]}}

``load_dataset(path)`` reads a bounded regular local UTF-8 JSON file;
``parse_dataset_json(raw)`` applies the same schema to bytes or text. Schema 2
requires a fourth nonempty ``regression`` split with the same task fields; schema
1 remains exactly the three original splits. The result
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
_ALL_SPLITS = _SPLITS + ('regression',)


def _schema_splits(version):
    if type(version) is not int or version not in (1, 2):
        raise ValueError('dataset schema version 1 or 2 required')
    return _SPLITS if version == 1 else _ALL_SPLITS

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
    regression_tasks: tuple = field(default=(), repr=False)
    schema_version: int = 1

    def telemetry(self):
        """Counts and identity only; no source text, questions or expected answers."""
        return {'dataset_id': self.dataset_id, 'digest': self.digest,
                'schema_version': self.schema_version,
                'counts': {split: len(getattr(self.manifest, split))
                           for split in _schema_splits(self.schema_version)}}


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
    splits = _schema_splits(record['schema_version'])
    _identifier(record['dataset_id'])
    _keys(record['source'], ('uri', 'revision'))
    for name in ('uri', 'revision'):
        _text(record['source'][name], limit=2048 if name == 'uri' else 256)
        if any(c.isspace() for c in record['source'][name]):
            raise ValueError('source URI and revision must be explicit single identifiers')
    _keys(record['splits'], splits)
    count = 0
    for split in splits:
        tasks = record['splits'][split]
        if type(tasks) is not list or not tasks:
            raise ValueError('all dataset splits require nonempty task arrays')
        count += len(tasks)
        if count > max_tasks:
            raise ValueError('dataset exceeds task cap')
    seen_ids, seen_instructions, family_splits = set(), set(), {}
    frozen, families = {}, []
    for split in splits:
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
    manifest = DatasetManifest(*(tuple(task.task_id for task in frozen[split]) for split in splits))
    digest = sha256(json.dumps(record, sort_keys=True, separators=(',', ':'),
                              ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    return FrozenCueDataset(record['dataset_id'], record['source']['uri'], record['source']['revision'],
                            digest, manifest, *(frozen[split] for split in _SPLITS), tuple(families),
                            regression_tasks=frozen.get('regression', ()), schema_version=record['schema_version'])


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


def validate_dataset(dataset):
    """Revalidate a supplied frozen object before durable study reservations.

    A dataclass constructor or ``dataclasses.replace`` is not an attestation.
    Rebuild the strict source schema from actual task/family content, reparse it,
    then require matching digest, manifest, ordering and every frozen field.
    Return the freshly validated object. No expected answers leave this function.
    """
    if type(dataset) is not FrozenCueDataset or type(dataset.manifest) is not DatasetManifest:
        raise ValueError('exact frozen dataset and manifest records required')
    splits = _schema_splits(dataset.schema_version)
    if type(dataset.regression_tasks) is not tuple or (dataset.schema_version == 1 and dataset.regression_tasks):
        raise ValueError('regression tasks require dataset schema version 2')
    if type(dataset.digest) is not str or not re.fullmatch(r'[a-f0-9]{64}', dataset.digest):
        raise ValueError('canonical dataset digest required')
    _identifier(dataset.dataset_id)
    _text(dataset.source_uri, limit=2048)
    _text(dataset.source_revision, limit=256)
    if type(dataset.families) is not tuple or not len(splits) <= len(dataset.families) <= MAX_DATASET_TASKS:
        raise ValueError('bounded immutable task family records required')
    family_by_task = {}
    content_bytes = len(dataset.dataset_id.encode()) + len(dataset.source_uri.encode()) + len(dataset.source_revision.encode())
    for entry in dataset.families:
        if type(entry) is not tuple or len(entry) != 3:
            raise ValueError('exact task, family, split tuple required')
        task_id, family_id, split = entry
        _identifier(task_id); _identifier(family_id)
        if type(split) is not str or split not in splits or task_id in family_by_task:
            raise ValueError('duplicate or invalid task family mapping')
        family_by_task[task_id] = (family_id, split)
        content_bytes += len(task_id.encode()) + len(family_id.encode()) + len(split.encode())
        if content_bytes > MAX_DATASET_BYTES:
            raise ValueError('dataset exceeds byte cap')
    reconstructed = {}
    count = 0
    for split in splits:
        tasks = getattr(dataset, split + '_tasks')
        manifest_ids = getattr(dataset.manifest, split)
        if type(tasks) is not tuple or not tasks or type(manifest_ids) is not tuple:
            raise ValueError('immutable nonempty dataset partitions required')
        count += len(tasks)
        if count > MAX_DATASET_TASKS:
            raise ValueError('dataset exceeds task cap')
        records = []
        for task in tasks:
            if type(task) is not ExperimentTask:
                raise ValueError('exact experiment task records required')
            _identifier(task.task_id)
            _text(task.instruction, limit=65536)
            _text(task.expected, limit=65536)
            membership = family_by_task.get(task.task_id)
            if membership is None or membership[1] != split:
                raise ValueError('missing or mismatched task family mapping')
            content_bytes += len(task.instruction.encode()) + len(task.expected.encode())
            if content_bytes > MAX_DATASET_BYTES:
                raise ValueError('dataset exceeds byte cap')
            records.append({'task_id': task.task_id, 'family_id': membership[0],
                            'instruction': task.instruction, 'expected': task.expected})
        reconstructed[split] = records
    if count != len(family_by_task):
        raise ValueError('extra or missing task family mappings')
    schema = {'schema_version': dataset.schema_version, 'dataset_id': dataset.dataset_id,
              'source': {'uri': dataset.source_uri, 'revision': dataset.source_revision},
              'splits': reconstructed}
    checked = parse_dataset_json(json.dumps(schema, sort_keys=True, separators=(',', ':'),
                                           ensure_ascii=False, allow_nan=False))
    if checked != dataset:
        raise ValueError('dataset digest, manifest, order or content differs from canonical data')
    return checked
