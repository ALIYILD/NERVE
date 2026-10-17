#!/usr/bin/env python3
"""Read-only source preflight and audit-view export. Does not launch inference."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from nerve_awim.memory_gateway.contracts import MemoryScope
from nerve_awim.memory_gateway.experience_store_v2 import ExperienceStoreV2
from nerve_awim.memory_gateway.experience_study_store_v2 import ExperienceStudyStoreV2
from nerve_awim.memory_gateway.overnight_advisors import summarize, jev_prior
from nerve_awim.obsidian_export_v18 import render_research_snapshot


def hashed(path):
    return sha256(path.read_bytes()).hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True)+'\n')
    temporary.replace(path)


def validated_store(path, kind):
    before = hashed(path)
    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True) as db:
        scope = json.loads(db.execute('SELECT scope FROM metadata WHERE id=1').fetchone()[0])
        store = object.__new__(kind)
        store.scope = MemoryScope(**scope)
        episodes, head = store._validate(db)
    if hashed(path) != before:
        raise ValueError('experience_store_changed_during_read')
    return dict(name=path.parent.name, sha256=before, data=dict(head=head, episodes=episodes))


def require_cycle_admission(root, shared, authorization, connection, model_digest):
    """Bind startup to a specific operator preflight and unchanged focused evidence.

    These records are local evidence, not a human signature or promotion authority.
    """
    checks = json.loads((root/'research/overnight-20261017/cycle-readiness.json').read_text())
    pins = checks.get('source_sha256', {})
    required = {'scripts/overnight_cycle.py', 'scripts/overnight_cycle_preflight.py'}
    if (checks.get('tests_passed') is not True or not required <= pins.keys()
            or any(hashed(root/name) != expected for name, expected in pins.items())):
        raise ValueError('cycle_focused_evidence_stale')
    for name in ('log', 'receipt'):
        if hashed(root/checks[name]) != checks[name+'_sha256']:
            raise ValueError('cycle_focused_evidence_tampered')
    rows = [json.loads(line) for line in (shared/'ledger.jsonl').read_text().splitlines() if line.strip()]
    matching = [(i, row) for i, row in enumerate(rows) if row.get('event') == 'preflight_ok'
                and row.get('pod_id') == connection['pod_id']]
    if not matching:
        raise ValueError('current_preflight_ok_missing')
    index, row = matching[-1]
    fingerprint = sha256(json.dumps(row, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    replay_hash = row.get('replay_hash', '')
    if (row.get('issued_by') != 'operator' or row.get('digest') != model_digest
            or not isinstance(replay_hash, str) or len(replay_hash) != 64
            or any(c not in '0123456789abcdef' for c in replay_hash)
            or authorization.get('preflight_event_sha256') != fingerprint):
        raise ValueError('current_preflight_binding_required')
    for later in rows[index+1:]:
        if (later.get('event') in ('preflight_failed', 'pod_marked_unusable')
                and later.get('pod_id') == connection['pod_id']):
            raise ValueError('preflight_superseded_by_failure')
    # The dev executor acquires its own O_EXCL lock immediately before SSH.
    # Do not consume advisor calls while another worker/preflight owns the pod.
    if (shared/'pod-B.lock').exists():
        raise ValueError('pod_B_busy')
    return fingerprint


def run(shared, runs, vault):
    paths = json.loads((ROOT/'docs/galahad/evidence/overnight-protected-paths.json').read_text())['paths']
    mismatches = [p for p, h in paths.items() if hashed(ROOT/p) != h]
    if mismatches:
        raise ValueError('protected_integrity_failure:'+','.join(mismatches))
    ledger_path = shared/'ledger.jsonl'
    ledger = [json.loads(line) for line in ledger_path.read_text().splitlines() if line.strip()]
    snapshots = [dict(name='orchestration ledger', sha256=hashed(ledger_path), data=ledger)]
    for name, kind in [('scientific-format-episodes-v1', ExperienceStoreV2),
                       ('overnight-20261017-b-experiences', ExperienceStudyStoreV2),
                       ('overnight-20261017-B01b-experiences', ExperienceStudyStoreV2),
                       ('overnight-20261017-A01-planned', ExperienceStudyStoreV2)]:
        snapshots.append(validated_store(runs/name/'experiences.sqlite', kind))
    rows = [json.loads(line) for line in (ROOT/'research/leaderboard-20261017.jsonl').read_text().splitlines() if line.strip()]
    report = summarize(rows)
    save(ROOT/'research/calibration-20261017.json', report)
    # This is a fixture readiness check, not a historical experiment's prior.
    import os
    fixture = None
    if not os.environ.get('TYPESAFE_API_KEY'):
        aggregate = dict(completion=0, abort=0, violations=0, goal_penalized=0, prediction_penalized=0)
        fixture = jev_prior(aggregate, {'readiness_only': aggregate}, lambda _: None)
        save(ROOT/'research/overnight-20261017/jev-offline-fixture.json',
             dict(advisor_prior=fixture, scope='readiness-only; not scored against historical verdicts'))
    reasons = []
    if (shared/'inference-revoked.json').exists():
        reasons.append('W0_global_inference_revocation_present')
    if not (shared/'pod-B.lock').exists():
        reasons.append('pod_B_not_acquired')
    readiness=ROOT/'research/overnight-20261017/cycle-readiness.json'
    if not readiness.exists():
        reasons.append('cycle_focused_validation_pending')
    else:
        checks=json.loads(readiness.read_text())
        if checks.get('tests_passed') is not True or any(hashed(ROOT/name)!=h for name,h in checks['source_sha256'].items()):
            reasons.append('cycle_validation_missing_or_source_changed')
    if not (shared/'W2-cycle-resume-authorization.json').exists():
        reasons.append('W0_scoped_cycle_admission_missing')
    status = dict(timestamp=datetime.now(timezone.utc).isoformat(), status='not_running',
                  reasons=reasons, protected_files_checked=len(paths), protected_mismatches=[],
                  experience_chains_validated=len(snapshots)-1,
                  existing_leaderboard_rows=len(rows), new_cycle_verdict_rows=0,
                  advisor_prior_mode='no-live-jev' if fixture else 'live_key_present_not_called',
                  model_calls=0, lock_acquired=False, holdout_opened=False,
                  calibration='no_prospective_verdicts', spend_updated=False,
                  vault=str(vault), program_sha256=hashed(ROOT/'research/program-20261017.md'))
    save(ROOT/'research/status-20261017.json', status)
    snapshots.append(dict(name='W2 cycle status', sha256=hashed(ROOT/'research/status-20261017.json'), data=status))
    vault.mkdir(parents=True, exist_ok=True)
    (vault/'.obsidian').mkdir(exist_ok=True)
    view=vault/'W2-20261017.md'
    view.write_text(render_research_snapshot(snapshots)+'\n')
    return status


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--shared', type=Path, default=Path.home()/'nerve-orchestration')
    parser.add_argument('--runs', type=Path, default=Path.home()/'nerve-research-runs')
    parser.add_argument('--vault', type=Path, default=Path.home()/'nerve-research-runs/obsidian-audit-vault')
    args=parser.parse_args()
    print(json.dumps(run(args.shared, args.runs, args.vault), sort_keys=True))
