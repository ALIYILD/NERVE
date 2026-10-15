"""Registered failure diagnosis after verified WorldCore research rejection."""
import json
from pathlib import Path
import sqlite3
from hashlib import sha256

from . import worldcore_study
from . import worldcore_diagnostics


def _sources():
    return {name: sha256((worldcore_study.ROOT / name).read_bytes()).hexdigest()
            for name in ('src/nerve_awim/memory_gateway/research_followup.py',
                         'scripts/diagnose_worldcore_research.py')}


def run_followup(directory, predecessor):
    """Consume one verified predecessor; diagnose only the registered failure."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=False)
    database = root / 'followup.sqlite'
    with sqlite3.connect(database) as db:
        db.execute('CREATE TABLE nodes(name TEXT PRIMARY KEY,status TEXT,evidence TEXT)')
        db.execute('INSERT INTO nodes VALUES (?, ?, NULL)', ('verify_predecessor', 'claimed'))
    sources = _sources()
    node = 'verify_predecessor'
    try:
        source = Path(predecessor)
        report = json.loads((source / 'report.json').read_text())
        worldcore_study.validate_receipt(source, report, worldcore_study.manifest())
        digest = sha256(worldcore_study._json(report).encode()).hexdigest()
        with sqlite3.connect(database) as db:
            db.execute('UPDATE nodes SET status=?,evidence=? WHERE name=?', ('complete', digest, node))
        if report['result']['status'] != 'no_deployable_improvement':
            result = {'status': 'no_registered_diagnostic', 'predecessor_sha256': digest,
                      'deployed': False, 'goal_achieved': False}
        else:
            node = 'outage_feasibility'
            with sqlite3.connect(database) as db:
                db.execute('INSERT INTO nodes VALUES (?, ?, NULL)', (node, 'claimed'))
            diagnosis = worldcore_diagnostics.run_diagnostic(root / 'diagnostic')
            worldcore_diagnostics.validate_receipt(root / 'diagnostic', diagnosis)
            # Recheck predecessor after diagnosis; no evaluation is repeated.
            worldcore_study.validate_receipt(source, report, worldcore_study.manifest())
            result = {'status': 'diagnosed', 'predecessor_sha256': digest,
                      'diagnosis': diagnosis, 'deployed': False, 'goal_achieved': False,
                      'automatic_retry': False,
                      'next_action': 'Design a prospective observation-recovery experiment; preserve outage safety gates.'}
            with sqlite3.connect(database) as db:
                db.execute('UPDATE nodes SET status=?,evidence=? WHERE name=?', ('complete', worldcore_study._json(diagnosis), node))
        if _sources() != sources:
            raise ValueError('followup_source_drift')
        result['source_sha256'] = sources
        (root / 'report.json').write_text(worldcore_study._json(result) + '\n')
        return result
    except BaseException as exc:
        with sqlite3.connect(database) as db:
            db.execute('UPDATE nodes SET status=?,evidence=? WHERE name=?', ('failed_consumed', type(exc).__name__, node))
        raise
