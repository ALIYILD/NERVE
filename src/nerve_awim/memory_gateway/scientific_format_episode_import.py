"""Import four verified format-probe outcomes without inference or reward writes."""
from hashlib import sha256
from pathlib import Path
import stat

from . import scientific_candidate_format_study as study
from . import scientific_episode_import as legacy
from .experience_store_v2 import ExperienceStoreV2
from .contracts import MemoryScope
from .scientific_structured_tasks import parse_shape
from .research_supervisor import _exclusive

pilot=study.pilot
canonical,digest,_save_exact=legacy.canonical,legacy.digest,legacy._save_exact
REVISION='scientific-format-episode-import-v1'
SCOPE=MemoryScope('synthetic-science','model-research','format-episodes')
STRATA={'supported':'supported-measurement','unit_mismatch':'unit-mismatch'}


def sources():
    pins=legacy.sources();pins.update(study.sources())
    for name in ('src/nerve_awim/memory_gateway/scientific_format_episode_import.py',
                 'src/nerve_awim/memory_gateway/experience_store_v2.py',
                 'scripts/import_scientific_format_episodes.py'):
        pins[name]=sha256((pilot.ROOT/name).read_bytes()).hexdigest()
    return pins


def episodes(report,pins):
    """Recompute shape and contract scores; malformed output has unknown factual support."""
    rows=report['rows']
    if (report['status']!='complete' or len(rows)!=4
            or canonical([(r['task_id'],r['constrained']) for r in rows])!=canonical(study.PAIRS)):
        raise ValueError('fixed_complete_four_pair_roster_required')
    receipt_hash=digest(report);result=[]
    for ordinal,row in enumerate(rows):
        task_id,constrained=row['task_id'],row['constrained']
        if type(constrained) is not bool:raise ValueError('boolean_arm_required')
        task=study.tasks()[task_id];raw=row['response']['raw_output'];score=study.score(raw,task_id)
        if canonical(row['score'])!=canonical(score):raise ValueError('historical_score_changed')
        policy=digest({'base_candidate_config':report['protocol']['config'],
                       'constrained':constrained,'model_digest':report['protocol']['expected_digest']})
        if row['arm_config_sha256']!=policy:raise ValueError('arm_identity_changed')
        if not score['schema_valid']:failure='schema_shape_failure'
        elif not score['format_valid']:
            shape=parse_shape(raw)
            failure='abstention_contract_failure' if shape['status']=='abstain' and any(shape[k] for k in shape if k!='status') else 'format_failure'
        elif task['expected']['status']=='answer' and parse_shape(raw)['status']=='abstain':failure='supported_abstention'
        elif not score['strict_correct']:failure='incorrect_selection'
        else:failure='none'
        result.append(dict(episode_id=digest({'revision':REVISION,'receipt':receipt_hash,'ordinal':ordinal}),
            context_hash=digest(task['evidence']),inputs_hash=digest({'query':task['query'],'evidence':task['evidence']}),
            agent=SCOPE.agent_id,candidate_id='constrained' if constrained else 'unrestricted',policy_version=policy,
            action='inference',output=raw,evaluator_verdict='strict_correct' if score['strict_correct'] else 'strict_incorrect',
            format_ok=score['format_valid'],schema_ok=score['schema_valid'],
            evidence_ok=score['strict_correct'] if score['format_valid'] else None,
            real_world_outcome=None,outcome_source='synthetic_evaluator',timestamps=None,
            source_sha256=pins,source_receipt_sha256=receipt_hash,source_ordinal=ordinal,
            stratum=STRATA[task_id],failure_class=failure,synthetic_only=True,source_kind='scientific_format_probe_v1'))
    return result


def run(directory, study_directory, study_journal, expected_digest, *, disabled=False):
    if type(disabled) is not bool:
        raise ValueError('boolean_disabled_required')
    if disabled:
        return {'status': 'off', 'reason': 'disabled', 'new_model_calls': 0}
    pins = sources()
    report = study.validate_receipt(study_directory, expected_digest, study_journal)
    rows = episodes(report, pins)
    if sources() != pins:
        raise ValueError('source_code_changed')
    root = Path(directory).resolve()
    source_directory = Path(study_directory).resolve()
    source_journal = Path(study_journal).resolve()
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
        store = ExperienceStoreV2(store_path, gateway, SCOPE)
        if not store_path.exists(): store.initialize(proposer)
        result = dict(version=REVISION, status='complete', source_receipt_sha256=digest(report),
            study_directory=str(source_directory), study_journal=str(source_journal),
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
        checked = study.validate_receipt(study_directory, expected_digest, study_journal)
        if canonical(checked) != canonical(report) or sources() != pins:
            raise ValueError('source_receipt_changed_during_import')
        store.export(reader, root / 'episodes.jsonl')
        if sources() != pins:
            raise ValueError('source_code_changed')
        checked = study.validate_receipt(study_directory, expected_digest, study_journal)
        if canonical(checked) != canonical(report) or sources() != pins:
            raise ValueError('source_receipt_changed_during_import')
        _save_exact(report_path, result)
        return result
