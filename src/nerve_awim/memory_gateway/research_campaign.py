"""Bounded, durable supervision of one registered synthetic research experiment.

This does not train model weights, promote policies, or execute generated code.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
from hashlib import sha256
import json
import multiprocessing
import os
from pathlib import Path
import re
import sqlite3
import time
import tempfile

from . import online_adaptation_study as study


def _json(value):
    return json.dumps(value, sort_keys=True, allow_nan=False)


def _manifest(cycles, seeds_per_cycle, first_seed, timeout, interval=0):
    if type(cycles) is not int or not 1 <= cycles <= 32:
        raise ValueError('cycles must be 1..32')
    if type(seeds_per_cycle) is not int or not 1 <= seeds_per_cycle <= 4:
        raise ValueError('seeds_per_cycle must be 1..4')
    if type(first_seed) is not int or not 10000 <= first_seed <= 2**31-129:
        raise ValueError('fresh first_seed must be 10000..2147483519')
    if type(timeout) not in (int, float) or not 1 <= timeout <= 300:
        raise ValueError('trial timeout must be 1..300 seconds')
    if type(interval) not in (int, float) or not 0 <= interval <= 1800:
        raise ValueError('cycle interval must be 0..1800 seconds')
    original = study.protocol_manifest()
    seeds = list(range(first_seed, first_seed + cycles*seeds_per_cycle))
    return {'experiment': 'fixed-online-adaptation-campaign-v1', 'cycles': cycles, 'cycle_interval_seconds': interval,
        'seeds_per_cycle': seeds_per_cycle, 'seeds': seeds, 'trial_timeout_seconds': timeout,
        'arms': list(study.ARMS), 'scenarios': list(study.SCENARIOS),
        'episodes_per_trial': study.EPISODES,
        'max_pipeline_episodes': len(seeds)*len(study.ARMS)*len(study.SCENARIOS)*study.EPISODES,
        'baseline': original['baseline'], 'candidate': original['candidate'],
        'source_sha256': {**original['source_sha256'],
            'research_campaign.py': sha256(Path(__file__).read_bytes()).hexdigest(),
            '../../../scripts/run_research_campaign.py': sha256((Path(__file__).parents[3]/'scripts/run_research_campaign.py').read_bytes()).hexdigest()},
        'dataset_sha256': sha256(_json([(s, c, study._cases(s, c)) for s in seeds
                                      for c in study.SCENARIOS]).encode()).hexdigest(),
        'public_synthetic_nonsealed': True, 'promotion_authorized': False}



def _current_sources(protocol):
    root = Path(__file__).parent
    return {name: sha256((root/name).read_bytes()).hexdigest()
            for name in protocol['source_sha256']}

def _child(connection, seed, scenario, arm):
    try:
        connection.send(('ok', study._trial(seed, scenario, arm)))
    except BaseException:
        connection.send(('error', 'trial_failed'))
    finally:
        connection.close()


def _execute(seed, scenario, arm, timeout):
    context = multiprocessing.get_context('spawn')
    reader, writer = context.Pipe(duplex=False)
    process = context.Process(target=_child, args=(writer, seed, scenario, arm))
    try:
        process.start()
        writer.close()
        if not reader.poll(timeout):
            raise TimeoutError('trial_timeout')
        status, result = reader.recv()
        if status != 'ok':
            raise RuntimeError('trial_failed')
        return result
    finally:
        if process.pid is not None:
            if process.is_alive():
                process.terminate()
            process.join(1)
            if process.is_alive():
                process.kill()
                process.join(1)
        reader.close()
        writer.close()


@contextmanager
def _ownership(path):
    with open(str(path)+'.lock', 'a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError('campaign ledger is already owned') from error
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _export(path, report):
    destination = Path(path)
    descriptor, name = tempfile.mkstemp(prefix=destination.name+'.', suffix='.tmp', dir=destination.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'w') as handle:
            handle.write(_json(report)+'\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def run_campaign(database, output, *, run_id, deadline, stop_file, cycles=8,
                 seeds_per_cycle=4, first_seed=10000, trial_timeout=60, cycle_interval=0):
    return _run(database, output, run_id=run_id, deadline=deadline, stop_file=stop_file,
                cycles=cycles, seeds_per_cycle=seeds_per_cycle, first_seed=first_seed,
                trial_timeout=trial_timeout, cycle_interval=cycle_interval, executor=_execute)


def _run(database, output, *, run_id, deadline, stop_file, cycles=8,
         seeds_per_cycle=4, first_seed=10000, trial_timeout=60, cycle_interval=0, executor=_execute):
    if not isinstance(run_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', run_id):
        raise ValueError('invalid run identifier')
    if not isinstance(deadline, datetime) or deadline.tzinfo is None or deadline.utcoffset().total_seconds() != 0:
        raise ValueError('deadline must be timezone-aware UTC')
    paths = [Path(p).resolve() for p in (database, output, stop_file)]
    auxiliary = [Path(str(paths[0])+suffix) for suffix in ('.lock', '-journal', '-wal', '-shm')] + [Path(str(paths[1])+'.lock')]
    if len(set(paths+auxiliary)) != len(paths+auxiliary):
        raise ValueError('database, output, stop file and ledger auxiliary paths must differ')
    database, output, stop_file = paths
    protocol = _manifest(cycles, seeds_per_cycle, first_seed, trial_timeout, cycle_interval)
    report = {'run_id': run_id, 'protocol': protocol, 'deadline_utc': deadline.isoformat(),
        'status': 'running', 'phase': 'claimed', 'completed_cycles': 0, 'cycle_summaries': [], 'trials': [], 'claimed_pipeline_episodes': 0,
        'completed_pipeline_episodes': 0, 'recommendation': 'incomplete_no_recommendation',
        'deployed': False, 'model_weights_trained': False, 'promotion_authorized': False,
        'scope': 'Public synthetic policy research; no general model or scientific discovery claim.',
        'learning_scope': 'Each trial starts a fresh learner. Cycles replicate fixed policies; learning is within trials only, not persistent across cycles.'}
    with _ownership(database), _ownership(output), sqlite3.connect(database) as connection:
        connection.executescript('''
            CREATE TABLE IF NOT EXISTS research_campaign_runs (
              run_id TEXT PRIMARY KEY, status TEXT NOT NULL, report TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS research_campaign_seeds (
              seed INTEGER PRIMARY KEY, run_id TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS research_campaign_trials (
              seed INTEGER NOT NULL, scenario TEXT NOT NULL, arm TEXT NOT NULL,
              run_id TEXT NOT NULL, status TEXT NOT NULL, evidence TEXT,
              PRIMARY KEY(seed, scenario, arm));
        ''')
        # The exclusive lock proves any previously running owner is gone. Never replay it.
        old = connection.execute("SELECT run_id, report FROM research_campaign_runs WHERE status='running'").fetchall()
        for old_id, old_json in old:
            old_report = json.loads(old_json)
            old_report['status'] = 'interrupted_consumed'
            for trial in old_report.get('trials', []):
                if trial.get('status') == 'pending':
                    trial['status'] = 'interrupted_consumed'
            connection.execute('UPDATE research_campaign_runs SET status=?, report=? WHERE run_id=?',
                               ('interrupted_consumed', _json(old_report), old_id))
        connection.execute("UPDATE research_campaign_trials SET status='interrupted_consumed' WHERE status='pending'")
        connection.commit()
        if output.exists():
            raise FileExistsError('report already exists; choose a fresh output')
        try:
            with connection:
                connection.execute('INSERT INTO research_campaign_runs VALUES (?,?,?)',
                                   (run_id, 'running', _json(report)))
                connection.executemany('INSERT INTO research_campaign_seeds VALUES (?,?)',
                                       [(s, run_id) for s in protocol['seeds']])
        except sqlite3.IntegrityError as error:
            raise ValueError('run or seed range already consumed') from error

        def checkpoint():
            connection.execute('UPDATE research_campaign_runs SET status=?, report=? WHERE run_id=?',
                               (report['status'], _json(report), run_id))
            connection.commit()
            _export(output, report)

        def summarize_cycle(number):
            rows = [trial for trial in report['trials'] if trial['cycle'] == number]
            expected = seeds_per_cycle*len(study.SCENARIOS)*len(study.ARMS)
            if len(rows) != expected or any(trial['status'] != 'complete' for trial in rows):
                raise RuntimeError('incomplete cycle cannot be summarized')
            totals = {arm: {scenario: sum(trial['evidence']['hits'] for trial in rows
                      if trial['arm'] == arm and trial['scenario'] == scenario)
                      for scenario in study.SCENARIOS} for arm in study.ARMS}
            deltas = {scenario: totals['candidate'][scenario]-totals['baseline'][scenario]
                      for scenario in study.SCENARIOS}
            report['cycle_summaries'].append({'cycle': number, 'scenario_hits': totals,
                'scenario_deltas': deltas, 'tasks_per_arm': seeds_per_cycle*len(study.SCENARIOS)*study.EPISODES,
                'recommendation': 'candidate_for_review' if sum(deltas.values()) > 0 and min(deltas.values()) >= 0 else 'retain_baseline',
                'promotion_authorized': False, 'selection': 'fixed hypothesis; no tuning'})
            report['completed_cycles'] = number

        active = None
        try:
            checkpoint()
            for position, seed in enumerate(protocol['seeds']):
                if position and position % seeds_per_cycle == 0:
                    summarize_cycle(position//seeds_per_cycle)
                    report['phase'] = 'waiting_between_cycles'
                    checkpoint()
                    until = time.monotonic()+cycle_interval
                    while time.monotonic() < until and not stop_file.exists() and time.time() < deadline.timestamp():
                        time.sleep(min(1, until-time.monotonic(), max(0, deadline.timestamp()-time.time())))
                for scenario in study.SCENARIOS:
                    for arm in study.ARMS:
                        if stop_file.exists():
                            report['status'] = 'stopped_consumed'
                            checkpoint()
                            return report
                        remaining = deadline.timestamp() - time.time()
                        if remaining <= 0:
                            report['status'] = 'deadline_consumed'
                            checkpoint()
                            return report
                        if _current_sources(protocol) != protocol['source_sha256']:
                            raise RuntimeError('source_or_protocol_drift')
                        report['phase'] = 'executing_trial'
                        active = {'cycle': position//seeds_per_cycle+1, 'seed': seed,
                                  'scenario': scenario, 'arm': arm, 'status': 'pending'}
                        connection.execute('INSERT INTO research_campaign_trials VALUES (?,?,?,?,?,?)',
                                           (seed, scenario, arm, run_id, 'pending', None))
                        report['trials'].append(active)
                        report['claimed_pipeline_episodes'] += study.EPISODES
                        checkpoint()  # durable claim before any tool execution
                        remaining = deadline.timestamp()-time.time()
                        if remaining <= 0 or stop_file.exists():
                            raise TimeoutError('deadline_or_stop_after_claim')
                        started = time.monotonic()
                        row = study._validate(executor(seed, scenario, arm, min(trial_timeout, remaining)),
                                              seed, scenario, arm)
                        if _current_sources(protocol) != protocol['source_sha256']:
                            raise RuntimeError('source_or_protocol_drift')
                        active.update(status='complete', evidence=row, elapsed_seconds=time.monotonic()-started)
                        connection.execute('UPDATE research_campaign_trials SET status=?, evidence=? WHERE seed=? AND scenario=? AND arm=?',
                                           ('complete', _json(row), seed, scenario, arm))
                        report['completed_pipeline_episodes'] += study.EPISODES
                        checkpoint()
                        active = None
            summarize_cycle(cycles)
            totals = {a: {s: sum(t['evidence']['hits'] for t in report['trials']
                      if t['arm'] == a and t['scenario'] == s) for s in study.SCENARIOS} for a in study.ARMS}
            deltas = {s: totals['candidate'][s]-totals['baseline'][s] for s in study.SCENARIOS}
            report.update(status='complete', phase='finished', completed_cycles=cycles, scenario_hits=totals, scenario_deltas=deltas,
                          tasks_per_arm=len(protocol['seeds'])*len(study.SCENARIOS)*study.EPISODES,
                          recommendation='candidate_for_review' if sum(deltas.values()) > 0 and min(deltas.values()) >= 0 else 'retain_baseline')
            checkpoint()
            return report
        except BaseException as error:
            report['status'] = 'failed_consumed'
            report['error'] = ('interrupted' if isinstance(error, (KeyboardInterrupt, SystemExit)) else
                               'trial_timeout' if isinstance(error, TimeoutError) else 'evaluation_aborted')
            if active:
                active.update(status='failed_consumed', error=report['error'])
                connection.execute('UPDATE research_campaign_trials SET status=?, evidence=? WHERE seed=? AND scenario=? AND arm=?',
                                   ('failed_consumed', _json(active), active['seed'], active['scenario'], active['arm']))
            checkpoint()
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise
            return report
