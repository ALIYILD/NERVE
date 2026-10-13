"""Verified prediction-only findings in scoped memory; no control promotion."""
import gzip
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from .gateway import MemoryGateway
from .contracts import MemoryRequest
from . import phase_forecast_study as study
from . import phase_forecast_episode as replay
from . import recovery_adaptation as recovery

ONLINE_SOURCES = ('src/nerve_awim/forecast_runtime.py',
                  'src/nerve_awim/memory_gateway/online_forecast_demo.py',
                  'scripts/demo_online_forecast.py')
EVALUATOR = 'verified-forecast-receipt-v1'
TABLE = 'forecast_memory_receipts_v1'


def _json(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def _pins():
    return {name:sha256((study.recovery.ROOT/name).read_bytes()).hexdigest() for name in ONLINE_SOURCES}


def _require(condition):
    if not condition: raise ValueError('invalid_online_forecast_evidence')


def validate_online(raw,summary):
    """Validate stored trace and forecasts, not absent comparison-state payloads."""
    report = json.loads(raw)
    _require(summary['report_sha256'] == sha256(raw).hexdigest())
    _require(summary['new_source_sha256'] == _pins())
    _require(type(report) is dict and set(report) == {'protocol','status','rows','online_episodes',
        'comparison_episodes','plant_steps','performance_improvement_claimed','candidate_promoted',
        'model_weights_trained','deployed','scope'})
    _require(report['protocol'] == 'online-forecast-development-demo-v1' and report['status'] == 'complete')
    for key,value in (('online_episodes',4),('comparison_episodes',8),('plant_steps',960)):
        _require(type(report[key]) is int and report[key] == value)
    for key in ('performance_improvement_claimed','candidate_promoted','model_weights_trained','deployed'):
        _require(report[key] is False)
    _require(type(report['rows']) is list and len(report['rows']) == 4)
    expected = [(9,s,a) for s in ('stationary','drift') for a in (False,True)]
    summaries = []
    for row,(seed,scenario,adaptive) in zip(report['rows'],expected):
        _require(type(row) is dict and set(row) == {'seed','scenario','adaptive','online',
            'original_trajectory_sha256','trajectory_unchanged','controller_states_unchanged',
            'online_matches_replay','metrics'})
        _require(type(row['seed']) is int and row['seed'] == seed and row['scenario'] == scenario
                 and row['adaptive'] is adaptive)
        online = row['online']
        _require(type(online) is dict and set(online) == {'episode','forecasts','controller_states','enabled'})
        _require(online['enabled'] is True)
        recovery.validate(online['episode'],seed,scenario,adaptive)
        expected_forecasts = replay.replay(replay.project(online['episode']['trace']))
        _require(_json(online['forecasts']) == _json(expected_forecasts))
        _require(_json(row['metrics']) == _json(replay.score(online['episode']['trace'],expected_forecasts)))
        _require(row['original_trajectory_sha256'] == sha256(_json(online['episode']).encode()).hexdigest())
        # These are recorded driver claims, not independently reconstructed proof.
        for key in ('trajectory_unchanged','controller_states_unchanged','online_matches_replay'):
            _require(type(row[key]) is bool)
        _require(type(online['controller_states']) is list and len(online['controller_states']) == 80)
        summaries.append({key:value for key,value in row.items() if key != 'online'})
    _require(_json(summary['cases']) == _json(summaries))
    for key,value in report.items():
        if key != 'rows': _require(_json(summary[key]) == _json(value))
    return report


def verified_fact(*,directory,claims,predecessor_path,source_paths,online_artifact,online_summary):
    paths = [Path(directory)/'report.json',Path(online_artifact),Path(online_summary)]
    snapshots = [path.read_bytes() for path in paths]
    pins = study._sources(); online_pins = _pins()
    study.validate_receipt(directory,claims,predecessor_path,source_paths)
    report = json.loads(snapshots[0])
    if (report['recommendation'] != 'forecast_candidate_for_review' or report['holdout_consumed'] is not True
            or set(report['stages']) != {'train','validation','holdout'}
            or any(stage['passed'] is not True for stage in report['stages'].values())):
        raise ValueError('positive_forecast_receipt_required')
    raw = gzip.decompress(snapshots[1]) if snapshots[1].startswith(b'\x1f\x8b') else snapshots[1]
    online = validate_online(raw,json.loads(snapshots[2]))
    if (pins != study._sources() or online_pins != _pins()
            or snapshots != [path.read_bytes() for path in paths]):
        raise ValueError('forecast_evidence_changed')
    study_digest = sha256(_json(report).encode()).hexdigest()
    online_digest = sha256(_json(online).encode()).hexdigest()
    # One scoped claim per verified study, independent of unverified auxiliary
    # state payloads or online evidence formatting. Online digest is provenance.
    identity = sha256(_json({'study':study_digest,'bridge':'forecast-outcome-memory-v1'}).encode()).hexdigest()
    fact = {'kind':'verified_synthetic_forecast_outcome','protocol':'forecast-outcome-memory-v1',
        'receipt_sha256':identity,'study_sha256':study_digest,'online_sha256':online_digest,
        'episodes':report['episodes'],'holdout_consumed':True,
        'recommendation':'forecast_candidate_requires_independent_review',
        'stage_mae_gain':{name:stage['sum_stratum_mae_gain'] for name,stage in report['stages'].items()},
        'online_recorded_cases':4,'recorded_forecasts_replay_equivalent':True,
        'control_objective_improvement_established':False,'comparison_states_independently_reconstructed':False,
        'candidate_promoted':False,'model_weights_trained':False,
        'interpretation':'Synthetic prediction-only finding. Online trace and forecast replay validated; absent comparison states not reconstructed. No control, clinical, or deployment authority.'}
    content = _json(fact)
    if len(content) > 2048: raise ValueError('forecast_fact_too_large')
    return 'forecast-receipt:'+identity,content


class ForecastOutcomeMemory:
    def __init__(self,gateway):
        if type(gateway) is not MemoryGateway: raise TypeError('authoritative memory gateway required')
        self.gateway = gateway

    def claim(self,reader,scope,source):
        self.gateway._require(reader,scope,'read')
        with sqlite3.connect(Path(self.gateway.ledger.path).resolve().as_uri()+'?mode=ro',uri=True) as db:
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(TABLE,)).fetchone()
            if exists is None: return None
            result = db.execute('SELECT status,memory_id FROM forecast_memory_receipts_v1 WHERE tenant=? AND agent=? AND context=? AND source=?',
                (scope.tenant_id,scope.agent_id,scope.context,source)).fetchone()
        self.gateway._require(reader,scope,'read')
        return result

    def approved(self,reader,scope,**evidence):
        gateway = self.gateway
        gateway._require(reader,scope,'read')
        source,content = verified_fact(**evidence)
        digest = json.loads(content)['receipt_sha256']
        with gateway._lock:
            result = gateway.retrieve(reader,MemoryRequest(scope,digest,limit=20,max_context_chars=32768))
            records = [r for r in result.records if r.kind == 'episodic' and r.source_id == source
                       and r.content == content and r.evaluator_id == EVALUATOR and r.outcome_score is None]
            if len(records) != 1: return None
            if self.claim(reader,scope,source) != ('proposed',records[0].memory_id): return None
            return records[0]

    def propose(self,proposer,scope,**evidence):
        gateway = self.gateway
        gateway._require(proposer,scope,'propose'); gateway._require(proposer,scope,'read')
        if 'approve' in proposer.permissions: raise PermissionError('use a proposal-only host capability')
        source,content = verified_fact(**evidence)
        identity = (scope.tenant_id,scope.agent_id,scope.context,source)
        with gateway._lock:
            gateway._require(proposer,scope,'propose'); gateway._require(proposer,scope,'read')
            with sqlite3.connect(gateway.ledger.path) as db:
                db.execute('CREATE TABLE IF NOT EXISTS forecast_memory_receipts_v1(tenant TEXT,agent TEXT,context TEXT,source TEXT,status TEXT,memory_id TEXT,PRIMARY KEY(tenant,agent,context,source))')
                try: db.execute('INSERT INTO forecast_memory_receipts_v1 VALUES(?,?,?,?,?,NULL)',(*identity,'claimed'))
                except sqlite3.IntegrityError as exc: raise ValueError('forecast_receipt_already_consumed') from exc
            try:
                memory_id = gateway.propose(proposer,scope=scope,content=content,source_id=source,kind='episodic')
                with sqlite3.connect(gateway.ledger.path) as db:
                    db.execute('UPDATE forecast_memory_receipts_v1 SET status=?,memory_id=? WHERE tenant=? AND agent=? AND context=? AND source=?',('proposed',memory_id,*identity))
                return memory_id
            except BaseException:
                with sqlite3.connect(gateway.ledger.path) as db:
                    db.execute('UPDATE forecast_memory_receipts_v1 SET status=? WHERE tenant=? AND agent=? AND context=? AND source=?',('failed_consumed',*identity))
                raise

    def review(self,reviewer,scope,memory_id,**evidence):
        gateway = self.gateway
        gateway._require(reviewer,scope,'approve'); gateway._require(reviewer,scope,'read')
        if 'propose' in reviewer.permissions: raise PermissionError('use a review-only host capability')
        source,content = verified_fact(**evidence)
        with gateway._lock:
            gateway._require(reviewer,scope,'approve')
            record = gateway._record_in_scope(reviewer,memory_id,scope)
            if (record.status != 'pending' or record.kind != 'episodic' or record.source_id != source
                    or record.content != content or record.source_sha256 != sha256(content.encode()).hexdigest()):
                raise ValueError('forecast_memory_does_not_match_verified_receipt')
            if self.claim(reviewer,scope,source) != ('proposed',memory_id):
                raise ValueError('forecast_proposal_not_reviewable')
            return gateway.decide(reviewer,memory_id,scope=scope,approve=True,evaluator_id=EVALUATOR)
