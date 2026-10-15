"""Import verified historical synthetic outputs without inference or reward writes."""
from hashlib import sha256
import json
import os
import stat
from pathlib import Path

from . import scientific_interface_validation as validation
from . import scientific_interface_validation_tasks as tasks
from . import scientific_model_learning as pilot
from .contracts import MemoryScope
from .experience_store import ExperienceStore
from .research_supervisor import _exclusive

REVISION = 'scientific-episode-import-v1'
SCOPE = MemoryScope('synthetic-science', 'model-research', 'episodes')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


def sources():
    result = validation.sources()
    for name in ('src/nerve_awim/memory_gateway/scientific_episode_import.py',
                 'src/nerve_awim/memory_gateway/experience_store.py',
                 'scripts/import_scientific_episodes.py'):
        result[name] = sha256((pilot.ROOT / name).read_bytes()).hexdigest()
    return result


def episodes(report, pins):
    """Map already validated rows; format failures make evidence agreement unknown.

    evidence_ok describes agreement with the frozen synthetic answer contract,
    not a clinical/factual adjudication of arbitrary prose. Conflict failure
    classification records a non-abstaining response, including malformed text.
    """
    if [(r['task_id'], r['arm']) for r in report['rows']] != validation.pairs():
        raise ValueError('fixed_sixteen_pair_roster_required')
    receipt_hash = digest(report)
    result = []
    for ordinal, row in enumerate(report['rows']):
        task_id, arm = row['task_id'], row['arm']
        task = tasks._task(task_id)
        score = tasks.judge(row['raw_output'], task_id)
        if canonical(score) != canonical(row['score']):
            raise ValueError('historical_score_changed')
        output = row['raw_output']
        if tasks.STRATA[task_id] == 'conflict' and output.strip() != 'ABSTAIN':
            failure = 'conflict_non_abstaining'
        elif score['format_failure']:
            failure = 'format_failure'
        elif task['expected'] != 'ABSTAIN' and output.strip() == 'ABSTAIN':
            failure = 'supported_abstention'
        elif not score['strict_correct']:
            failure = 'incorrect_selection'
        else:
            failure = 'none'
        result.append(dict(
            episode_id=digest({'revision': REVISION, 'receipt': receipt_hash, 'ordinal': ordinal}),
            context_hash=row['evidence']['context_sha256'], agent=SCOPE.agent_id,
            candidate_id=arm,
            policy_version=digest({'arm': arm, 'protocol': report['protocol']}),
            inputs_hash=digest({'query': task['query'], 'evidence': task['evidence']}),
            action='inference', output=output,
            evaluator_verdict='strict_correct' if score['strict_correct'] else 'strict_incorrect',
            format_ok=not score['format_failure'],
            evidence_ok=None if score['format_failure'] else score['strict_correct'],
            real_world_outcome=None, outcome_source='synthetic_evaluator', timestamps=None,
            source_sha256=pins, stratum=tasks.STRATA[task_id], failure_class=failure,
            synthetic_only=True, source_kind='scientific_validation_v1'))
    return result


def _save_exact(path, payload):
    data = (canonical(payload) + '\n').encode()
    if path.exists() or path.is_symlink():
        mode = path.lstat()
        if not stat.S_ISREG(mode.st_mode) or stat.S_IMODE(mode.st_mode) != 0o600:
            raise ValueError('private_regular_report_required')
        if path.read_bytes() != data:
            raise ValueError('existing_import_report_changed')
        return
    temporary = path.with_suffix('.pending')
    if temporary.exists() or temporary.is_symlink():
        mode = temporary.lstat()
        if not stat.S_ISREG(mode.st_mode) or stat.S_IMODE(mode.st_mode) != 0o600:
            raise ValueError('private_regular_pending_report_required')
        with temporary.open('rb') as stream:
            if stream.read(len(data) + 1) != data:
                raise ValueError('pending_import_report_changed')
    else:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)


def run(directory, validation_directory, validation_journal, expected_digest, *, disabled=False):
    if type(disabled) is not bool:
        raise ValueError('boolean_disabled_required')
    if disabled:
        return {'status': 'off', 'reason': 'disabled', 'new_model_calls': 0}
    pins = sources()
    report = validation.validate_receipt(validation_directory, expected_digest, validation_journal)
    rows = episodes(report, pins)
    if sources() != pins:
        raise ValueError('source_code_changed')
    root = Path(directory).resolve()
    source_directory = Path(validation_directory).resolve()
    source_journal = Path(validation_journal).resolve()
    if root == source_directory or source_directory in root.parents or root in source_directory.parents or source_journal == root or root in source_journal.parents:
        raise ValueError('separate_import_directory_required')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if stat.S_IMODE(root.stat().st_mode) != 0o700:
        raise ValueError('private_import_directory_required')
    with _exclusive(root):
        store_path = root / 'experiences.sqlite'
        authority_path = root / 'authority.sqlite'
        if not store_path.exists() and any(path.name != 'supervisor.lock' for path in root.iterdir()):
            raise ValueError('existing_store_missing_degraded')
        if store_path.exists() and not authority_path.is_file():
            raise ValueError('existing_store_authority_missing')
        gateway, _, proposer, _, reader = pilot._state(authority_path)
        store = ExperienceStore(store_path, gateway, SCOPE)
        if not store_path.exists(): store.initialize(proposer)
        result = dict(version=REVISION, status='complete', source_receipt_sha256=digest(report),
            validation_directory=str(source_directory), validation_journal=str(source_journal),
            expected_digest=expected_digest, source_sha256=pins, episode_count=len(rows),
            episode_ids=[row['episode_id'] for row in rows], new_model_calls=0,
            rewards_written=False, approved_knowledge_written=False, synthetic_only=True,
            historical_timestamps_known=False)
        # Reject changed import identity before modifying an existing destination.
        report_path = root / 'report.json'
        if report_path.exists() or report_path.is_symlink():
            mode = report_path.lstat()
            if not stat.S_ISREG(mode.st_mode) or stat.S_IMODE(mode.st_mode) != 0o600:
                raise ValueError('private_regular_report_required')
        if report_path.exists() and report_path.read_bytes() != (canonical(result)+'\n').encode():
            raise ValueError('existing_import_report_changed')
        existing = store.query(reader)['episodes']
        expected_by_id = {row['episode_id']: row for row in rows}
        if any(row['episode_id'] not in expected_by_id or canonical(row) != canonical(expected_by_id[row['episode_id']]) for row in existing):
            raise ValueError('import_store_roster_changed')
        store.append_many(proposer, rows)
        exported = store.query(reader)
        if canonical(sorted(exported['episodes'], key=lambda row: row['episode_id'])) != canonical(sorted(rows, key=lambda row: row['episode_id'])):
            raise ValueError('import_store_roster_changed')
        checked = validation.validate_receipt(validation_directory, expected_digest, validation_journal)
        if canonical(checked) != canonical(report) or sources() != pins:
            raise ValueError('source_receipt_changed_during_import')
        store.export(reader, root / 'episodes.jsonl')
        if sources() != pins:
            raise ValueError('source_code_changed')
        checked = validation.validate_receipt(validation_directory, expected_digest, validation_journal)
        if canonical(checked) != canonical(report) or sources() != pins:
            raise ValueError('source_receipt_changed_during_import')
        _save_exact(report_path, result)
        return result
