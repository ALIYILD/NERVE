#!/usr/bin/env python3
"""Create bounded, local specialist audits on the existing Hermes task board."""
import datetime
import argparse
import json
import os
from pathlib import Path
import sys
import re
import time
import subprocess
import tempfile

HOME = Path.home()
ACTIVE = ('triage', 'todo', 'scheduled', 'ready', 'running', 'blocked', 'review')
OUTCOMES = {'completed', 'blocked', 'crashed', 'timed_out', 'spawn_failed',
            'gave_up', 'reclaimed', 'released', 'failed', 'running', 'done'}
ROUTING_EVIDENCE_CONTRACT = (
    '/api/openrouter/status ok means only local API-key presence (Boolean(key)); '
    'it makes no provider request and proves neither provider reachability nor model availability. '
    'Only claim current catalog listing after reading the public https://openrouter.ai/api/v1/models '
    'catalog with a bounded request; catalog listing still does not prove successful inference. '
    'Actual execution remains unknown without an existing inference receipt. Do not run inference to test this. ')


def ensure_runtime(home, checkout, argv):
    """Use Hermes's already-provisioned interpreter; never install packages."""
    if os.environ.get('NERVE_MAINTENANCE_RUNTIME') == '1':
        return
    launcher = json.loads(subprocess.check_output(
        [str(home / '.local/bin/hermes'), '--print-runtime-command'],
        text=True, timeout=10))
    if not isinstance(launcher, list) or not launcher or not isinstance(launcher[0], str):
        raise RuntimeError('Unable to resolve the installed Hermes runtime launcher.')
    resolve = ('import sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); '
               'from pm.environments import project_python; print(project_python(Path(sys.argv[1])))')
    python = subprocess.check_output([launcher[0], '-I', '-c', resolve, str(checkout)],
                                     text=True, timeout=10).strip()
    if not Path(python).is_absolute() or not Path(python).is_file():
        raise RuntimeError('The provisioned Hermes interpreter is unavailable; repair the local runtime first.')
    env = dict(os.environ, NERVE_MAINTENANCE_RUNTIME='1', HERMES_DISABLE_LAZY_INSTALLS='1')
    os.execve(python, [python, str(Path(__file__).resolve()), *argv], env)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent,
                                     prefix=path.name+'.', suffix='.tmp', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(json.dumps(value, indent=2) + '\n')
            stream.flush()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def configured_models(home):
    """Read configuration, returning only model IDs, never credentials."""
    try:
        import hermes_yaml as yaml
    except ImportError:
        import yaml
    config = json.loads((home / '.agentic-os/free-model-config.json').read_text())
    route = config.get('openrouter', {})
    models = [route.get('model')] if route.get('enabled') is True else []
    try:
        profile = yaml.safe_load((home / '.hermes/profiles/coordinator/config.yaml').read_text())
    except yaml.YAMLError:
        raise ValueError('Invalid coordinator YAML configuration; check it locally.') from None
    primary = profile.get('model', {})
    if isinstance(primary, dict) and primary.get('provider') == 'openrouter':
        models.append(primary.get('default'))
    for entry in profile.get('fallback_providers', []):
        if isinstance(entry, str):
            models.append(entry)
        elif isinstance(entry, dict) and entry.get('provider', 'openrouter') == 'openrouter':
            models.append(entry.get('model'))
    return [model for model in models if isinstance(model, str)]


def refresh_catalog(catalog):
    """Fetch public pricing metadata only; no credentials or inference requests."""
    try:
        raw = subprocess.check_output([
            '/usr/bin/curl', '--disable', '--fail', '--silent', '--show-error',
            '--max-time', '20', '--max-filesize', '5000000',
            'https://openrouter.ai/api/v1/models'], timeout=25, stderr=subprocess.DEVNULL)
        if len(raw) > 5000000:
            raise ValueError('oversized catalog')
        data = json.loads(raw)
        if not isinstance(data, dict) or not isinstance(data.get('data'), list):
            raise ValueError('invalid catalog')
        available = []
        for row in data['data']:
            if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id'].endswith(':free'):
                continue
            pricing = row.get('pricing')
            if not isinstance(pricing, dict):
                continue
            try:
                free = all(type(pricing.get(key)) in (str, int, float) and float(pricing[key]) == 0
                           for key in ('prompt', 'completion'))
            except (ValueError, OverflowError):
                free = False
            if free:
                available.append(row['id'])
        if not available:
            raise ValueError('no verified free models')
        write_json(catalog, sorted(set(available)))
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        raise ValueError('Refresh the NERVE free-model catalog failed; check metadata connectivity before retrying. No work was admitted.') from None


def resolve_model(home, requested=None, *, now=None):
    catalog = home / '.agentic-os/nerve/free-models.json'
    now = time.time() if now is None else now
    if not catalog.exists() or not 0 <= now - catalog.stat().st_mtime <= 86400:
        refresh_catalog(catalog)
    available = json.loads(catalog.read_text())
    if not isinstance(available, list) or not all(isinstance(m, str) and m.endswith(':free') for m in available):
        raise ValueError('Invalid NERVE free-model catalog; refresh it before retrying.')
    candidates = configured_models(home)
    if requested is not None:
        candidates = [requested] if requested in candidates else []
    model = next((m for m in candidates if m.endswith(':free') and m in available), None)
    if model is None:
        raise ValueError('Configure an available OpenRouter free model, then retry with --model or the configured default.')
    return model


def blockers(conn):
    rows = conn.execute("""SELECT t.id, t.assignee, t.status,
        (SELECT COALESCE(r.outcome,r.status) FROM task_runs r
         WHERE r.task_id=t.id ORDER BY r.id DESC LIMIT 1)
        FROM tasks t WHERE t.status NOT IN ('done','archived') OR t.status IS NULL
        ORDER BY t.id""").fetchall()
    return [dict(id=row[0], profile=row[1], status=row[2] if row[2] in ACTIVE else 'unknown',
                 latest_outcome=row[3] if row[3] in OUTCOMES else 'unknown') for row in rows]


def connect_board(kanban, connector=None):
    """Installed Hermes splits connection APIs; retain injected test adapters."""
    if connector is not None:
        return connector.connect(board='agentos-maintenance')
    return kanban.connect()


def main(argv=None, *, home=HOME, kanban=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-key')
    parser.add_argument('--model', help='Configured, catalog-verified OpenRouter free model only')
    parser.add_argument('--evidence', type=Path, help='Compact host-produced maintenance JSON snapshot')
    args = parser.parse_args(argv)
    day = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d')
    run_key = args.run_key or day
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', run_key):
        raise ValueError('Invalid mission run key')
    dest = home / 'AgentOS-Vault/Journal/maintenance-missions' / run_key
    manifest = dest / 'mission.json'
    if manifest.exists():
        print(json.dumps({'skipped': 'Today already has a mission', 'manifest': str(manifest)})); return
    connector = None
    if kanban is None:
        os.environ.setdefault('HERMES_HOME', str(home / '.hermes/profiles/coordinator'))
        os.environ['HERMES_KANBAN_BOARD'] = 'agentos-maintenance'
        checkout = home / '.hermes/hermes-agent'
        checkout = checkout if checkout.is_dir() else home / 'hermes-agent'
        ensure_runtime(home, checkout, sys.argv[1:] if argv is None else argv)
        sys.path.insert(0, str(checkout))
        from hermes_cli import kanban_db as kanban
        from hermes_cli import kanban_db_connect as connector
    conn = connect_board(kanban, connector)
    try:
        existing = blockers(conn)
        if existing:
            receipt = {'status':'blocked_existing_work', 'runKey':run_key,
                       'date':day, 'board':'agentos-maintenance', 'tasks':existing,
                       'next_action':'Review existing task evidence; retry or resolve explicitly with the supported board API.'}
            write_json(dest.parent / 'admission-status.json', receipt)
            print(json.dumps(receipt))
            conn.close()
            return receipt
        try:
            model = resolve_model(home, args.model)
        except (ValueError, OSError, ImportError, TypeError, AttributeError):
            write_json(dest.parent / 'admission-status.json', {
                'status':'blocked_configuration','runKey':run_key,'date':day,
                'board':'agentos-maintenance',
                'next_action':'Refresh the NERVE free-model catalog and configure an available OpenRouter free model.'})
            raise
        if args.evidence is None:
            args.evidence = dest / 'maintenance-evidence.json'
            subprocess.run([sys.executable, str(home / 'nerve-review/scripts/agentos_maintenance.py'),
                            '--output', str(args.evidence)], check=True, timeout=30,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        raw = args.evidence.read_bytes()
        if len(raw) > 100000:
            raise ValueError('Maintenance evidence must be at most 100000 bytes.')
        evidence = json.loads(raw)
        if not isinstance(evidence, dict):
            raise ValueError('Maintenance evidence must be a JSON object.')
        collected = evidence.get('collected_at_epoch')
        if (type(evidence.get('schema_version')) is not int or evidence['schema_version'] != 1
                or type(collected) is not int or not -60 <= time.time() - collected <= 86400):
            raise ValueError('Collect fresh schema_version 1 maintenance evidence before creating work.')
    except BaseException:
        conn.close()
        raise
    dest.mkdir(parents=True, exist_ok=True)
    write_json(dest / 'maintenance-evidence.json', evidence)
    boundaries = ('Work locally and read-only outside the output directory. Never send messages, post comments, close issues, push, deploy, purchase, change credentials, or edit production code. Do not call paid models or delegate more workers. Use terminal/file tools only when needed. Keep each report under 1000 words. If a check is unavailable, say so. Do not claim a check passed without its evidence. ')
    goal = (f'Agent OS daily operational audit for {day}. {boundaries} Output directory: {dest}. '
            'Workers produce routing.json and scheduling.json. QA must independently read both files and write verification.json with boolean accepted, checks, and issues. '
            'Accept only when both worker reports are valid JSON, each includes evidence and honest pass/fail/unknown states, and no paid routes or unsafe schedules were activated. '
            'Coordinator reads all three files and writes summary.md listing completed checks, remaining blockers, and next action; never call an unaccepted mission verified. ')
    routing = (boundaries + f'Write {dest}/routing.json. Read http://127.0.0.1:3737/api/openrouter/status and ~/.agentic-os/free-model-config.json. '
               + ROUTING_EVIDENCE_CONTRACT + 'Report primary model, judge default from /Users/aliyildirim/agent-os-runtime/source/src/lib/freeModels.ts, free fallbacks, and whether all automatic defaults are free. Include evidence paths/URLs and status pass/fail/unknown. A configured :free suffix shows configuration only, not current provider availability or actual historical execution. Separate configured routing from observed availability and execution; mark absent evidence unknown. Do not expose keys. Limit evidence gathering to these three local sources and, only if claiming current catalog listing, the public model catalog. ')
    scheduling = (boundaries + f'Write {dest}/scheduling.json. Read only {dest}/maintenance-evidence.json for operational evidence. '
                  'Report service health, enabled schedule count, next-run freshness, local delivery, last execution receipts, and blocked tasks across every board where present in the snapshot. Include evidence paths and status pass/fail/unknown. Missing or stale evidence is unknown. Do not claim no_paid_model_routes: this scheduling snapshot omits model/provider routing fields; record that claim as unknown or not assessed and leave routing verification to the routing worker. Do not enumerate boards, unblock tasks, or run old prompts. A healthy schedule may be due within the current 60-second tick. Project board blockers do not invalidate the Agent OS infrastructure audit; list them separately. ')
    def card(profile, title, body, parents=()):
        return kanban.create_task(conn, title=title + ' ' + day, body=body + '\n\n' + goal,
            assignee=profile, created_by='coordinator', workspace_kind='dir', workspace_path=str(dest),
            parents=parents, max_runtime_seconds=240, max_retries=1,
            model_override=model, provider_override='openrouter',
            idempotency_key='agentos-' + profile + '-' + run_key)
    try:
        worker_ids = [card('dashboard-operator', 'Check free model routing', routing),
                      card('workflow-integrity-auditor', 'Check scheduler and blocked queues', scheduling)]
        verifier_id = card('qa-release', 'Verify operational receipts',
            boundaries + f'Read {dest}/routing.json and {dest}/scheduling.json. Independently verify each critical claim against its underlying evidence, including {dest}/maintenance-evidence.json for scheduling. A worker assertion is not independent evidence. If the underlying source omits a field, mark that claim unknown; never infer no_paid_model_routes from a snapshot without model/provider fields. For routing, inspect the sources named by the routing worker directly. {ROUTING_EVIDENCE_CONTRACT}Distinguish configured :free model names from current provider availability and actual execution; configuration alone proves neither. Write {dest}/verification.json with accepted (boolean), checks (array), and issues (array). Use false when a required check fails, is unsupported, or is unknown.', worker_ids)
        synthesizer_id = card('coordinator', 'Summarize operational audit',
            boundaries + f'Read {dest}/routing.json, scheduling.json, verification.json. Write {dest}/summary.md with results, blockers and next action. Keep it concise.', [verifier_id])
    finally:
        conn.close()
    write_json(manifest, {'date':day,'runKey':run_key,'goal':goal,'outputs':str(dest),
        'model':model,'evidence':str(dest / 'maintenance-evidence.json'),
        'worker_ids':worker_ids,'verifier_id':verifier_id,'synthesizer_id':synthesizer_id})
    write_json(dest.parent / 'admission-status.json', {
        'status':'created','runKey':run_key,'date':day,'board':'agentos-maintenance',
        'manifest':str(manifest),'model':model})
    print(manifest.read_text())


if __name__ == '__main__':
    main()
