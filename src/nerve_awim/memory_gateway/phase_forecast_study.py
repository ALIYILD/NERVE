"""Fixed prediction-only routing study; no controller or promotion authority."""
from hashlib import sha256
import json
import math
import multiprocessing
from pathlib import Path
import sqlite3
import time

from . import observer_reanalysis as predecessor
from . import phase_forecast_episode as worker
from . import recovery_adaptation_study as recovery

SPLITS = {'train': tuple(range(44001,44009)), 'validation': tuple(range(45001,45009)),
          'holdout': tuple(range(46001,46017))}
ARMS = predecessor.study.ARMS
SCENARIOS = recovery.SCENARIOS
PATH_KEYS = {'study','claims','coordinator_directory','coordinator_journal'}


def _sources():
    pins = predecessor._sources()
    for name in ('src/nerve_awim/phase_forecast.py',
                 'src/nerve_awim/memory_gateway/phase_forecast_episode.py',
                 'src/nerve_awim/memory_gateway/phase_forecast_study.py',
                 'scripts/run_phase_forecast_study.py'):
        pins[name] = sha256((recovery.ROOT/name).read_bytes()).hexdigest()
    return pins


def manifest():
    return {'protocol':'phase-forecast-study-v1','splits':SPLITS,'arms':ARMS,
        'scenarios':SCENARIOS,'max_episodes':512,'max_plant_steps':40960,
        'child_timeout_seconds':30,'elapsed_budget_seconds':1800,
        'source_sha256':_sources(),'plant':recovery.manifest()['plant'],
        'routing':'Preserve controller forecasts exactly; use actual-action observer only for external-supervisor forecasts',
        'acceptance':'Every arm/regime routed MAE <= legacy MAE + 1e-12; summed mean MAE gain > 1e-5; no missing forecasts or action changes; controller predictions exact',
        'selection':'One fixed router, all eight arms in each stage, no tuning or candidate selection',
        'promotion_authorized':False,'control_objective_improvement_claimed':False}


def _paths(paths):
    if type(paths) is not dict or set(paths) != PATH_KEYS:
        raise ValueError('explicit_predecessor_paths_required')
    return {key:str(Path(value).resolve()) for key,value in paths.items()}


def _verified_predecessor(path, paths):
    paths = _paths(paths)
    artifact = Path(path).resolve()
    before = artifact.read_bytes()
    pins = predecessor._sources()
    report = predecessor.run(paths['study'],paths['claims'],paths['coordinator_directory'],paths['coordinator_journal'])
    if (report['source_sha256'] != pins or predecessor._sources() != pins
            or before != (recovery._json(report)+'\n').encode() or artifact.read_bytes() != before):
        raise ValueError('invalid_observer_predecessor')
    return sha256(before).hexdigest()


def compare(rows):
    """Pair forecasts within trajectories; never compare counterfactual actions."""
    grouped = {(scenario,arm):[] for scenario in SCENARIOS for arm in ARMS}
    identities = set()
    preserved = True
    missing = 0
    actions_changed = False
    for row in rows:
        control = row['control']; episode = control['episode']
        identity = (episode['seed'],episode['scenario'],control['arm'])
        if identity in identities or identity[1:] not in grouped:
            raise ValueError('invalid_forecast_roster')
        identities.add(identity)
        metric = row['metrics']
        for name in ('legacy_mae','routed_mae'):
            if name == 'routed_mae' and metric[name] is None and type(metric['missing_forecasts']) is int and metric['missing_forecasts'] > 0:
                continue
            if type(metric[name]) not in (float,int) or not math.isfinite(metric[name]) or metric[name] < 0:
                raise ValueError('invalid_forecast_metric')
        if (type(metric['controller_predictions_preserved']) is not bool
                or type(metric['actions_changed']) is not bool
                or type(metric['missing_forecasts']) is not int or metric['missing_forecasts'] < 0):
            raise ValueError('invalid_forecast_metric')
        preserved &= metric['controller_predictions_preserved']
        missing += metric['missing_forecasts']
        actions_changed |= metric['actions_changed']
        grouped[identity[1:]].append((identity[0],metric))
    seed_sets = [{seed for seed,_ in items} for items in grouped.values()]
    if not seed_sets[0] or any(seeds != seed_sets[0] for seeds in seed_sets):
        raise ValueError('incomplete_forecast_roster')
    strata = []
    for (scenario,arm), items in grouped.items():
        legacy = sum(m['legacy_mae'] for _,m in items)/len(items)
        routed = (sum(m['routed_mae'] for _,m in items)/len(items)
                  if all(m['routed_mae'] is not None for _,m in items) else None)
        strata.append({'scenario':scenario,'arm':arm,'episodes':len(items),
                       'legacy_mae':legacy,'routed_mae':routed,'gain':legacy-routed if routed is not None else None,
                       'nonregression':routed is not None and routed <= legacy+1e-12})
    gain = sum(s['gain'] for s in strata) if all(s['gain'] is not None for s in strata) else None
    return {'passed':preserved and not actions_changed and missing == 0
                    and all(s['nonregression'] for s in strata) and gain is not None and gain > 1e-5,
            'strata':strata,'sum_stratum_mae_gain':gain,
            'controller_predictions_preserved':preserved,'missing_forecasts':missing,
            'actions_changed':actions_changed}


def _child(connection, seed, scenario, arm):
    try: connection.send(('ok',worker.execute(seed,scenario,arm)))
    except BaseException: connection.send(('failed',None))
    finally: connection.close()


def _execute(seed,scenario,arm,timeout=30):
    context = multiprocessing.get_context('spawn')
    reader,writer = context.Pipe(duplex=False)
    child = context.Process(target=_child,args=(writer,seed,scenario,arm))
    try:
        child.start(); writer.close()
        if not reader.poll(timeout): raise TimeoutError('episode_timeout')
        status,row = reader.recv()
        if status != 'ok': raise RuntimeError('episode_failed')
        return row
    finally:
        if child.pid is not None:
            if child.is_alive(): child.terminate()
            child.join(1)
            if child.is_alive(): child.kill(); child.join(1)
        reader.close(); writer.close()


def _dataset(protocol):
    return sha256(recovery._json({key:protocol[key] for key in ('splits','scenarios','plant')}).encode()).hexdigest()


def _assessment(rows):
    return {split:compare([r for r in rows if r['split'] == split])
            for split in SPLITS if any(r['split'] == split for r in rows)}


def work_summary(rows):
    return {split:{'episodes':len(subset),
                   'episode_elapsed_seconds':sum(r['elapsed_seconds'] for r in subset)}
            for split in SPLITS if (subset := [r for r in rows if r['split'] == split])}


def run_study(directory,claims,predecessor_path,source_paths):
    return _run(directory,claims,predecessor_path,source_paths,_execute)


def _run(directory,claims,predecessor_path,source_paths,execute):
    paths = _paths(source_paths)
    predecessor_path = str(Path(predecessor_path).resolve())
    root = Path(directory)
    root.mkdir(parents=True,exist_ok=False)
    root = root.resolve(); claims = Path(claims).resolve()
    if root == claims or root in claims.parents: raise ValueError('shared_claims_must_be_outside_run')
    protocol = manifest(); digest = _dataset(protocol)
    prior = _verified_predecessor(predecessor_path,paths)
    with sqlite3.connect(claims) as db:
        db.execute('CREATE TABLE IF NOT EXISTS phase_forecast_studies(dataset TEXT PRIMARY KEY,directory TEXT,status TEXT,protocol TEXT)')
        try: db.execute('INSERT INTO phase_forecast_studies VALUES(?,?,?,?)',(digest,str(root),'claimed',recovery._json(protocol)))
        except sqlite3.IntegrityError as exc: raise ValueError('dataset_already_consumed') from exc
    ledger = root/'ledger.sqlite'
    with sqlite3.connect(ledger) as db:
        db.executescript('CREATE TABLE trials(ordinal INTEGER PRIMARY KEY,split TEXT,seed INTEGER,scenario TEXT,arm TEXT,status TEXT,evidence TEXT); CREATE TABLE state(id INTEGER PRIMARY KEY,status TEXT,evidence TEXT); CREATE TABLE stages(split TEXT PRIMARY KEY,evidence TEXT);')
        db.execute('INSERT INTO state VALUES(1,?,NULL)',('claimed',))
    (root/'protocol.json').write_text(recovery._json(protocol)+'\n')
    rows = []; stages = {}; start = time.monotonic()
    try:
        for split,seeds in SPLITS.items():
            for seed in seeds:
                for scenario in SCENARIOS:
                    for arm in ARMS:
                        remaining = protocol['elapsed_budget_seconds']-(time.monotonic()-start)
                        if remaining <= 0 or len(rows) >= protocol['max_episodes']: raise RuntimeError('study_budget_exhausted')
                        if _sources() != protocol['source_sha256']: raise ValueError('source_drift')
                        ordinal = len(rows)+1
                        with sqlite3.connect(ledger) as db:
                            db.execute('INSERT INTO trials VALUES(?,?,?,?,?,?,NULL)',(ordinal,split,seed,scenario,arm,'claimed'))
                        row = execute(seed,scenario,arm,min(30,remaining))
                        worker.validate(row,seed,scenario,arm)
                        if time.monotonic()-start > protocol['elapsed_budget_seconds']: raise RuntimeError('study_budget_exhausted')
                        if _sources() != protocol['source_sha256']: raise ValueError('source_drift')
                        with sqlite3.connect(ledger) as db:
                            db.execute('UPDATE trials SET status=?,evidence=? WHERE ordinal=?',('complete',recovery._json(row),ordinal))
                        rows.append({'split':split,**row})
            stages[split] = compare([r for r in rows if r['split'] == split])
            with sqlite3.connect(ledger) as db:
                db.execute('INSERT INTO stages VALUES(?,?)',(split,recovery._json(stages[split])))
                db.execute('UPDATE state SET status=?,evidence=?',('stage_frozen',recovery._json(stages)))
            if not stages[split]['passed']: break
        if _verified_predecessor(predecessor_path,paths) != prior: raise ValueError('predecessor_changed')
        if _sources() != protocol['source_sha256']: raise ValueError('source_drift')
        report = {'status':'complete','protocol':protocol,'predecessor_sha256':prior,
            'predecessor_path':predecessor_path,'source_paths':paths,'dataset_sha256':digest,
            'stages':stages,'rows':rows,'episodes':len(rows),'plant_steps':80*len(rows),
            'measured_work':work_summary(rows),'holdout_consumed':'holdout' in stages,
            'recommendation':'forecast_candidate_for_review' if stages.get('holdout',{}).get('passed') else 'retain_legacy_forecast',
            'candidate_promoted':False,'control_objective_improvement_claimed':False,
            'deployed':False,'model_weights_trained':False,'goal_achieved':False}
        encoded = recovery._json(report)
        (root/'report.json').write_text(encoded+'\n')
        with sqlite3.connect(ledger) as db: db.execute('UPDATE state SET status=?,evidence=?',('complete',encoded))
        with sqlite3.connect(claims) as db: db.execute('UPDATE phase_forecast_studies SET status=? WHERE dataset=?',('complete',digest))
        validate_receipt(root,claims,predecessor_path,paths)
        return report
    except BaseException:
        with sqlite3.connect(ledger) as db:
            db.execute("UPDATE trials SET status='failed_consumed' WHERE status='claimed'")
            db.execute("UPDATE state SET status='failed_consumed'")
        with sqlite3.connect(claims) as db: db.execute("UPDATE phase_forecast_studies SET status='failed_consumed' WHERE dataset=?",(digest,))
        raise


def validate_receipt(directory,claims,predecessor_path,source_paths):
    root = Path(directory).resolve(); path = root/'report.json'; before = path.read_bytes()
    report = json.loads(before); protocol = manifest(); paths = _paths(source_paths)
    def require(condition):
        if not condition: raise ValueError('invalid_phase_forecast_receipt')
    require(recovery._json(report['protocol']) == recovery._json(protocol))
    require(recovery._json(json.loads((root/'protocol.json').read_text())) == recovery._json(protocol))
    require(report['predecessor_path'] == str(Path(predecessor_path).resolve()) and report['source_paths'] == paths)
    require(report['predecessor_sha256'] == _verified_predecessor(predecessor_path,paths))
    with sqlite3.connect((root/'ledger.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        states = db.execute('SELECT id,status,evidence FROM state').fetchall()
        frozen = dict(db.execute('SELECT split,evidence FROM stages').fetchall())
        journal = db.execute('SELECT ordinal,split,seed,scenario,arm,status,evidence FROM trials ORDER BY ordinal').fetchall()
    require(states == [(1,'complete',recovery._json(report))])
    stages = _assessment(report['rows'])
    require(recovery._json(stages) == recovery._json(report['stages']))
    require(frozen == {split:recovery._json(value) for split,value in stages.items()})
    expected = []
    for split,seeds in SPLITS.items():
        expected.extend((split,seed,scenario,arm) for seed in seeds for scenario in SCENARIOS for arm in ARMS)
        require(split in stages)
        if not stages[split]['passed']: break
    require(len(expected) == len(journal) == len(report['rows']))
    for ordinal,(identity,stored,row) in enumerate(zip(expected,journal,report['rows']),1):
        split,seed,scenario,arm = identity
        require(stored[:6] == (ordinal,split,seed,scenario,arm,'complete'))
        clean = dict(row); require(clean.pop('split') == split)
        worker.validate(clean,seed,scenario,arm)
        require(recovery._json(clean) == stored[6])
    require(recovery._json(work_summary(report['rows'])) == recovery._json(report['measured_work']))
    require(type(report['episodes']) is int and report['episodes'] == len(expected))
    require(type(report['plant_steps']) is int and report['plant_steps'] == 80*len(expected))
    require(report['holdout_consumed'] is ('holdout' in stages))
    recommendation = 'forecast_candidate_for_review' if stages.get('holdout',{}).get('passed') else 'retain_legacy_forecast'
    require(report['recommendation'] == recommendation and report['status'] == 'complete')
    require(all(report[k] is False for k in ('deployed','model_weights_trained','goal_achieved','candidate_promoted','control_objective_improvement_claimed')))
    digest = _dataset(protocol); require(report['dataset_sha256'] == digest)
    with sqlite3.connect(Path(claims).resolve().as_uri()+'?mode=ro',uri=True) as db:
        claim = db.execute('SELECT directory,status,protocol FROM phase_forecast_studies WHERE dataset=?',(digest,)).fetchone()
    require(claim == (str(root),'complete',recovery._json(protocol)))
    require(_sources() == protocol['source_sha256'] and path.read_bytes() == before)
    return True
