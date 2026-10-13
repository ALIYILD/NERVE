"""Prospective matched recovery/learning study; fixed hypothesis, no promotion."""
from hashlib import sha256
import json
import math
import multiprocessing
from pathlib import Path
import sqlite3
import subprocess
import sys

from . import recovery_adaptation as episode
from . import worldcore_study

ROOT = worldcore_study.ROOT
SPLITS = {'validation': tuple(range(33001,33009)), 'holdout': tuple(range(34001,34017))}
SCENARIOS = ('stationary','drift')
SOURCES = worldcore_study.SOURCES + tuple('src/nerve_awim/'+name+'.py' for name in (
    'recovery_v21','recovery_v22','recovery_policy_v23','recovery_v24','recovery_v25',
    'identity_v26','runtime_v28','memory_gateway/recovery_adaptation',
    'memory_gateway/recovery_adaptation_study')) + (
    'scripts/verify_supervised_recovery.py','scripts/run_recovery_adaptation.py')


def _json(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def _sources():
    return {name:sha256((ROOT/name).read_bytes()).hexdigest() for name in SOURCES}


def manifest():
    return {'protocol':'recovery-adaptation-v1','splits':SPLITS,'scenarios':SCENARIOS,
        'arms':{'baseline':0.,'adaptive':.08},'steps_per_episode':80,
        'max_episodes':96,'max_plant_steps':7680,'episode_timeout_seconds':30,
        'source_sha256':_sources(),'fixed_hypothesis':True,'promotion_authorized':False,
        'plant':{'retention':.82,'stationary_gain':.27,'drift_gains':[.27,.48,.15,.4],
                 'gain_regime_steps':20,'target':1.2,'sensor_delay_steps':1,
                 'forced_dropout_origin_steps':[35,49],'random_dropout_probability':.12,
                 'position_noise_std':.03,'velocity_noise_std':.025},
        'controller':{'max_missing':5,'risk_aversion':.25,'estimator':'drift',
                      'recovery_samples':3,'evidence_minimum':2,'min_calibration_samples':6,
                      'safe_position':6.,'safe_velocity':2.,'horizon':3,'bound':6.},
        'comparison':'Frozen gain vs online gain; both arms retain adaptive filtering/calibration. Within-episode learning, not persistent cross-task training.',
        'acceptance':{'every_regime':'zero candidate envelope violations; active steps nondecreasing; external commands, prediction error and goal error nonincreasing',
                      'numerical_tolerance':1e-12,'strict_sum_regime_goal_gain':1e-5,
                      'online_updates_required':True},
        'holdout':'Only after validation gates; no parameter tuning; shared operator-owned dataset claim prevents repetition using that ledger',
        'scope':'Synthetic plant and host supervision; mock identity provider; external zero-input commands explicitly counted, not certified safe.'}


def compare(rows):
    """Frozen acceptance gates; every regime must retain correctness/cost."""
    if type(rows) is not list or not rows:
        raise ValueError('missing_comparison_rows')
    fields={'active_steps','supervisor_steps','violations','mean_goal_error','mean_prediction_error','successful_recoveries'}
    for row in rows:
        metrics=row['metrics']
        if (set(metrics)!=fields or any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in metrics.values())
                or any(type(metrics[k]) is not int or metrics[k]>80 for k in ('active_steps','supervisor_steps','violations','successful_recoveries'))
                or metrics['active_steps']+metrics['supervisor_steps']!=80
                or type(row['learning_updates']) is not int or row['learning_updates']<0):
            raise ValueError('invalid_comparison_metrics')
    keys=[(r['seed'],r['scenario'],r['adaptive']) for r in rows]
    if (any(type(r['seed']) is not int or type(r['adaptive']) is not bool
            or r['scenario'] not in SCENARIOS for r in rows) or len(set(keys))!=len(keys)):
        raise ValueError('invalid_comparison_identity')
    seeds=sorted({r['seed'] for r in rows})
    if set(keys)!={(seed,scenario,arm) for seed in seeds for scenario in SCENARIOS for arm in (False,True)}:
        raise ValueError('unmatched_comparison_arms')
    summaries={}
    for scenario in SCENARIOS:
        summaries[scenario]={}
        for adaptive in (False,True):
            items=[r['metrics'] for r in rows if r['scenario']==scenario and r['adaptive'] is adaptive]
            if not items:
                raise ValueError('missing_comparison_arm')
            summaries[scenario]['adaptive' if adaptive else 'baseline']={
                key:sum(r[key] for r in items)/len(items) for key in items[0]}
    reasons=[]
    paired=[]
    indexed={(r['seed'],r['scenario'],r['adaptive']):r for r in rows}
    for seed in seeds:
        for scenario in SCENARIOS:
            baseline=indexed[seed,scenario,False]['metrics']
            adaptive=indexed[seed,scenario,True]['metrics']
            paired.append({'seed':seed,'scenario':scenario,'adaptive_minus_baseline':
                           {key:adaptive[key]-baseline[key] for key in baseline}})
    if not any(r['learning_updates']>0 for r in rows if r['adaptive']):
        reasons.append('online_learning_not_exercised')
    gain=0.
    for scenario,arms in summaries.items():
        base,chosen=arms['baseline'],arms['adaptive']
        if chosen['violations'] != 0:
            reasons.append(scenario+':envelope_violation')
        for key,direction in (('active_steps',1),('supervisor_steps',-1),
                              ('mean_prediction_error',-1),('mean_goal_error',-1)):
            if direction*(chosen[key]-base[key]) < -1e-12:
                reasons.append(scenario+':regression:'+key)
        gain+=base['mean_goal_error']-chosen['mean_goal_error']
    if gain<=1e-5:
        reasons.append('no_strict_goal_gain')
    return {'passed':not reasons,'reasons':reasons,'summaries':summaries,
            'sum_regime_goal_gain':gain,'paired_deltas':paired}


def _child(connection,seed,scenario,adaptive):
    try:
        connection.send(('ok',episode.episode(seed,scenario,adaptive)))
    except BaseException:
        connection.send(('failed',None))
    finally:
        connection.close()


def _execute(seed,scenario,adaptive):
    context=multiprocessing.get_context('spawn')
    reader,writer=context.Pipe(duplex=False)
    process=context.Process(target=_child,args=(writer,seed,scenario,adaptive))
    try:
        process.start();writer.close()
        if not reader.poll(30):
            raise TimeoutError('episode_timeout')
        status,row=reader.recv()
        if status!='ok':
            raise RuntimeError('episode_failed')
        return row
    finally:
        if process.pid is not None:
            if process.is_alive():process.terminate()
            process.join(1)
            if process.is_alive():process.kill();process.join(1)
        reader.close();writer.close()


def _preflight(root):
    path=root/'recovery_preflight'
    # Only this registered repository script may run; no supplied command text.
    subprocess.run([sys.executable,str(ROOT/'scripts/verify_supervised_recovery.py'),
                    '--directory',str(path)],cwd=ROOT,check=True,timeout=30,
                   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    report=json.loads((path/'report.json').read_text())
    _validate_preflight(report,root)
    return report


def _validate_preflight(report,root):
    required={'stopped','fresh_samples','locked_before_approval','invalid_identity_denied',
              'approved','no_fabricated_actions','actual_action_resumed','old_epoch_rejected',
              'later_expiry','approval_replay_denied'}
    if (report['status']!='passed' or set(report['checks'])!=required
            or any(v is not True for v in report['checks'].values())
            or report['identity_provider']!='synthetic_fixture'):
        raise ValueError('invalid_recovery_preflight')
    names=['scripts/verify_supervised_recovery.py']+[
        'src/nerve_awim/'+name+'.py' for name in (
            'worldcore_v20','fusion_v12','recovery_v21','recovery_v22',
            'recovery_policy_v23','recovery_v24','recovery_v25','identity_v26',
            'runtime_v28','risk_v17','calibrated_v16','calibration_v15',
            'integrated_v13','drift_v14','adaptive_calibration_v19','coverage_v18')]
    expected={name:sha256((ROOT/name).read_bytes()).hexdigest() for name in names}
    stored=json.loads((Path(root)/'recovery_preflight/report.json').read_text())
    if _json(report)!=_json(stored) or report.get('source_sha256')!=expected:
        raise ValueError('invalid_preflight_provenance')
    return True


def run_study(directory,claim_database):
    return _run(directory,_execute,_preflight,claim_database)


def _claim(database,root,protocol):
    path=Path(database).resolve()
    if path==root or root in path.parents:
        raise ValueError('claim_ledger_must_be_outside_run_directory')
    dataset=sha256(_json({key:protocol[key] for key in ('splits','scenarios','arms','plant')}).encode()).hexdigest()
    identity=sha256(_json(protocol).encode()).hexdigest()
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS recovery_adaptation_claims (dataset_sha256 TEXT PRIMARY KEY, protocol_sha256 TEXT UNIQUE, directory TEXT, status TEXT)')
        try:
            db.execute('INSERT INTO recovery_adaptation_claims VALUES (?,?,?,?)',(dataset,identity,str(root),'claimed'))
        except sqlite3.IntegrityError as exc:
            raise ValueError('study_dataset_already_consumed') from exc
    return path,dataset



def _run(directory,execute,preflight,claim_database):
    root=Path(directory)
    root.mkdir(parents=True,exist_ok=False)
    root=root.resolve()
    protocol=manifest()
    claim_path,dataset=_claim(claim_database,root,protocol)
    database=root/'ledger.sqlite'
    (root/'protocol.json').write_text(_json(protocol)+'\n')
    with sqlite3.connect(database) as db:
        db.executescript('''CREATE TABLE study(id INTEGER PRIMARY KEY,status TEXT,protocol TEXT,report TEXT);
            CREATE TABLE trials(ordinal INTEGER PRIMARY KEY,split TEXT,seed INTEGER,scenario TEXT,
                                adaptive INTEGER,status TEXT,evidence TEXT);''')
        db.execute('INSERT INTO study VALUES (1,?,?,NULL)',('preflight_claimed',_json(protocol)))
    def check():
        if _sources()!=protocol['source_sha256']:
            raise ValueError('study_source_drift')
    rows=[]
    try:
        check()
        proof=preflight(root)
        check()
        with sqlite3.connect(database) as db:
            db.execute("UPDATE study SET status='validation_claimed',report=?",(_json({'preflight':proof}),))
        evaluations={}
        for split,seeds in SPLITS.items():
            for seed in seeds:
                for scenario in SCENARIOS:
                    for adaptive in (False,True):
                        check()
                        ordinal=len(rows)+1
                        if ordinal>protocol['max_episodes']:
                            raise RuntimeError('episode_budget_exhausted')
                        with sqlite3.connect(database) as db:
                            db.execute('INSERT INTO trials VALUES (?,?,?,?,?,?,NULL)',
                                       (ordinal,split,seed,scenario,int(adaptive),'claimed'))
                        try:
                            row=execute(seed,scenario,adaptive)
                            episode.validate(row,seed,scenario,adaptive)
                            check()
                        except BaseException:
                            with sqlite3.connect(database) as db:
                                db.execute("UPDATE trials SET status='failed_consumed' WHERE ordinal=?",(ordinal,))
                            raise
                        with sqlite3.connect(database) as db:
                            db.execute("UPDATE trials SET status='complete',evidence=? WHERE ordinal=?",(_json(row),ordinal))
                        rows.append({'split':split,**row})
            evaluations[split]=compare([r for r in rows if r['split']==split])
            if split=='validation':
                with sqlite3.connect(database) as db:
                    db.execute('UPDATE study SET status=?,report=?',
                        ('holdout_claimed' if evaluations[split]['passed'] else 'validation_rejected',
                         _json({'preflight':proof,'validation':evaluations[split],
                                'fixed_candidate':.08,'selection_frozen':True})))
                if not evaluations[split]['passed']:
                    break
        check()
        recommend=evaluations.get('holdout',{}).get('passed',False)
        report={'status':'complete','protocol':protocol,'preflight':proof,'evaluations':evaluations,
                'episodes':len(rows),'plant_steps':80*len(rows),'rows':rows,
                'holdout_consumed':'holdout' in evaluations,'dataset_sha256':dataset,
                'replay_protection':'Shared operator-owned claim ledger; deleting/replacing the ledger is not prevented',
                'recommendation':'candidate_for_review' if recommend else 'retain_baseline',
                'deployed':False,'model_weights_trained':False,'goal_achieved':False}
        with sqlite3.connect(database) as db:
            db.execute("UPDATE study SET status='complete',report=?",(_json(report),))
        with sqlite3.connect(claim_path) as db:
            db.execute("UPDATE recovery_adaptation_claims SET status='complete' WHERE dataset_sha256=?",(dataset,))
        (root/'report.json').write_text(_json(report)+'\n')
        validate_receipt(root,claim_path)
        return report
    except BaseException as exc:
        with sqlite3.connect(claim_path) as db:
            db.execute("UPDATE recovery_adaptation_claims SET status='failed_consumed' WHERE dataset_sha256=?",(dataset,))
        with sqlite3.connect(database) as db:
            db.execute("UPDATE study SET status='failed_consumed',report=?",(_json({'error_type':type(exc).__name__,'completed_episodes':len(rows)}),))
        raise


def validate_receipt(directory,claim_database):
    """Reconcile measured traces and decisions without repeating plant work."""
    def require(condition):
        if not condition:
            raise ValueError('invalid_study_receipt')
    root=Path(directory)
    try:
        report=json.loads((root/'report.json').read_text())
        protocol=manifest()
        _validate_preflight(report['preflight'],root)
        require(_json(report['protocol'])==_json(protocol))
        require(_json(json.loads((root/'protocol.json').read_text()))==_json(protocol))
        with sqlite3.connect((root/'ledger.sqlite').resolve().as_uri()+'?mode=ro',uri=True) as db:
            state=db.execute('SELECT status,protocol,report FROM study WHERE id=1').fetchone()
            journal=db.execute('SELECT ordinal,split,seed,scenario,adaptive,status,evidence FROM trials ORDER BY ordinal').fetchall()
        require(state[0]=='complete' and _json(json.loads(state[1]))==_json(protocol))
        require(_json(json.loads(state[2]))==_json(report))
        expected=[]
        for split,seeds in SPLITS.items():
            if split=='holdout' and not report['evaluations']['validation']['passed']:
                continue
            expected.extend((split,seed,scenario,adaptive) for seed in seeds for scenario in SCENARIOS for adaptive in (False,True))
        require(len(journal)==len(report['rows'])==len(expected))
        for n,(stored,row,identity) in enumerate(zip(journal,report['rows'],expected),1):
            split,seed,scenario,adaptive=identity
            require(stored[:6]==(n,split,seed,scenario,int(adaptive),'complete'))
            clean=dict(row)
            require(clean.pop('split')==split)
            require(_json(json.loads(stored[6]))==_json(clean))
            episode.validate(clean,seed,scenario,adaptive)
        evaluations={split:compare([r for r in report['rows'] if r['split']==split])
                     for split in SPLITS if any(r['split']==split for r in report['rows'])}
        require(_json(evaluations)==_json(report['evaluations']))
        require(_json(report['episodes'])==_json(len(expected)))
        require(_json(report['plant_steps'])==_json(80*len(expected)))
        require(report['holdout_consumed'] is ('holdout' in evaluations))
        recommend=evaluations.get('holdout',{}).get('passed',False)
        require(report['recommendation']==('candidate_for_review' if recommend else 'retain_baseline'))
        require(report['status']=='complete' and all(report[k] is False for k in ('deployed','model_weights_trained','goal_achieved')))
        dataset=sha256(_json({key:protocol[key] for key in ('splits','scenarios','arms','plant')}).encode()).hexdigest()
        require(report['dataset_sha256']==dataset)
        with sqlite3.connect(Path(claim_database).resolve().as_uri()+'?mode=ro',uri=True) as db:
            claim=db.execute('SELECT protocol_sha256,directory,status FROM recovery_adaptation_claims WHERE dataset_sha256=?',(dataset,)).fetchone()
        require(claim==(sha256(_json(protocol).encode()).hexdigest(),str(root.resolve()),'complete'))
        require(_sources()==protocol['source_sha256'])
        return True
    except (KeyError,TypeError,OSError,sqlite3.Error,json.JSONDecodeError) as exc:
        raise ValueError('invalid_study_receipt') from exc
