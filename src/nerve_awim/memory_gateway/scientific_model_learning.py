"""Eight claimed real-model training calls with authoritative strategy feedback."""
from dataclasses import asdict
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import re
import sqlite3
import time

from ..memory_v18 import MemoryAuthority, TrustedMemoryLedger
from . import scientific_measurement_tasks as tasks
from .automation import AutomaticLearningRun
from .contracts import MemoryRequest, MemoryScope
from .gateway import MemoryGateway
from .inference import LocalInferenceAdapter
from .learning import VerifiedOutcomeLearning
from .research_supervisor import _exclusive

ROOT = Path(__file__).resolve().parents[3]
MODEL = 'qwen2.5-coder:1.5b'
ORIGIN = 'http://127.0.0.1:11434'
REVISION = 'scientific-measurement-training-v1'
SCOPE = MemoryScope('synthetic-science','model-research','strategies')


def _json(value): return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def _hash(value): return sha256(_json(value).encode()).hexdigest()


def sources():
    names = ('memory_v18.py','memory_retrieval_v18.py','adaptive_memory.py',
        'memory_gateway/scientific_model_learning.py','memory_gateway/scientific_measurement_tasks.py',
        'memory_gateway/learning.py','memory_gateway/automation.py','memory_gateway/inference.py',
        'memory_gateway/gateway.py','memory_gateway/contracts.py','memory_gateway/policy.py',
        'memory_gateway/session.py','memory_gateway/research_supervisor.py',
        'memory_gateway/null_kv_adapter.py','memory_gateway/lifecycle.py','memory_gateway/observability.py')
    files = ['src/nerve_awim/'+name for name in names]+['scripts/run_scientific_model_learning.py',
        'scripts/benchmark_local_memory.py','scripts/probe_local_memory_readiness.py']
    return {name:sha256((ROOT/name).read_bytes()).hexdigest() for name in files}


def _helper(name):
    spec=importlib.util.spec_from_file_location('scientific_'+name,ROOT/'scripts'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def metadata(): return _helper('benchmark_local_memory').metadata()
def preload(): return _helper('probe_local_memory_readiness').preload()


def pairs():
    return [(task,strategy) for index,task in enumerate(tasks.TASKS)
            for strategy in (tuple(tasks.STRATEGIES) if index%2==0 else tuple(reversed(tasks.STRATEGIES)))]


class StrategyInference(LocalInferenceAdapter):
    def __init__(self,strategy):
        if strategy not in tasks.STRATEGIES: raise ValueError('registered_strategy_required')
        self.strategy=strategy
        super().__init__(base_url=ORIGIN,model=MODEL,max_output_tokens=128,
                         timeout_seconds=90,runtime_profile='cpu_research')
    def _model_response(self,query,context):
        return super()._model_response(tasks.STRATEGIES[self.strategy]+'\n'+query,context)


class ScientificLearningRun(AutomaticLearningRun):
    """Reuse host claims/budgets/status, replacing only email-specific execution."""
    def execute_pair(self,episode_id,task_id,strategy,memory_id,request,expected):
        if (task_id,strategy) not in pairs(): raise ValueError('registered_pair_required')
        self._check_access()
        task={'task_id':task_id,'strategy_id':strategy}
        self._claim(episode_id,_hash(task))
        try:
            record=self.learning._checked(memory_id)
            if record.content != strategy: raise ValueError('strategy_memory_mismatch')
            actual=self.learning.gateway.retrieve(self.reader,request)
            if (actual.source_digest != expected['digest'] or
                    [r.memory_id for r in actual.records] != expected['ids']):
                raise ValueError('evidence_order_or_digest_changed')
            start=time.perf_counter()
            response=StrategyInference(strategy).respond(self.learning.gateway,self.reader,request)
            usage=response['usage']
            if (response['status'] != 'generated_requires_review' or response['model'] != MODEL
                    or set(usage) != {'prompt_tokens','completion_tokens','total_tokens'}
                    or any(type(v) is not int or v < 0 for v in usage.values())
                    or usage['completion_tokens'] > 128
                    or usage['total_tokens'] != usage['prompt_tokens']+usage['completion_tokens']
                    or response['source_digest'] != expected['digest']
                    or [r['memory_id'] for r in response['records']] != expected['ids']):
                raise ValueError('measured_model_response_required')
            raw=response['output']
            if type(raw) is not str or not 1<=len(raw)<=16384:raise ValueError('bounded_raw_model_output_required')
            score=tasks.judge(raw,task_id)
            feedback=self.learning.observe(memory_id,episode_id,task,raw,expected_record=record)
            if feedback['status'] != 'judged' or feedback['success'] is not score['strict_correct']:
                raise ValueError('independent_feedback_mismatch')
            self._check_access()
            finished=self._finish(episode_id,'judged',feedback['success'],memory_id)
            return dict(task_id=task_id,strategy_id=strategy,episode_id=episode_id,
                raw_output=raw,score=score,usage=usage,model=response['model'],response_status=response['status'],source_digest=expected['digest'],
                evidence_ids=expected['ids'],elapsed_seconds=time.perf_counter()-start,
                feedback=finished)
        except BaseException:
            self._finish(episode_id,'execution_failed')
            raise


def _save(path,protocol,report):
    encoded=_json(report)
    with sqlite3.connect(path) as db:
        db.execute('UPDATE scientific_model_runs_v1 SET report=?,digest=? WHERE id=1',
                   (encoded,sha256(encoded.encode()).hexdigest()))


def _quarantine(path):
    if not Path(path).is_file():return
    with sqlite3.connect(path) as db:
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='memory_utility'").fetchone():
            db.execute("UPDATE memory_utility SET status='study_invalidated',success=NULL WHERE tenant=? AND agent=? AND revision=?",
                       (SCOPE.tenant_id,SCOPE.agent_id,REVISION))


def _state(path):
    authority=MemoryAuthority()
    proposer=authority.issue(SCOPE.tenant_id,SCOPE.agent_id,permissions=('read','propose'))
    reviewer=authority.issue(SCOPE.tenant_id,SCOPE.agent_id,permissions=('read','approve'))
    reader=authority.issue(SCOPE.tenant_id,SCOPE.agent_id,permissions=('read',))
    gateway=MemoryGateway(TrustedMemoryLedger(path,authority))
    learning=VerifiedOutcomeLearning(gateway,reviewer,SCOPE,tasks.evaluate,REVISION,
                                    window=4,max_observations=8)
    return gateway,learning,proposer,reviewer,reader


def _ranking(learning,reader,ids):
    records=[learning._checked(ids[strategy]) for strategy in tasks.STRATEGIES]
    for strategy,record in zip(tasks.STRATEGIES,records):
        if record.content!=strategy or record.source_id!='strategy-'+strategy:raise ValueError('strategy_record_changed')
    ranked=learning.ranker.rank(reader,records)
    with sqlite3.connect(learning.gateway.ledger.path) as db:
        scores=[]
        for record in ranked:
            results=db.execute("SELECT success FROM memory_utility WHERE memory=? AND revision=? AND status='judged' ORDER BY sequence DESC LIMIT 4",
                               (record.memory_id,REVISION)).fetchall()
            scores.append(dict(strategy=record.content,observations=len(results),successes=sum(r[0] for r in results),
                               training_utility=(1+sum(r[0] for r in results))/(2+len(results))))
    return scores


def _validate_complete(gateway,learning,reader,runner,report):
    if len(report['rows'])!=8 or [(r['task_id'],r['strategy_id']) for r in report['rows']]!=pairs():
        raise ValueError('incomplete_training_roster')
    if _json(report['ranking'])!=_json(_ranking(learning,reader,report['strategy_ids'])):raise ValueError('persistent_ranking_changed')
    if _json(report['summary'])!=_json(_summary(report['rows'])):raise ValueError('training_summary_changed')
    if (report['inference_attempts'],report['preload_attempts'],report['metadata_attempts'])!=(8,1,2):raise ValueError('call_budget_evidence_changed')
    if report['metadata_before']!=report['metadata_after'] or report['metadata_before']!={'model':MODEL,'digest':report['protocol']['expected_digest']}:
        raise ValueError('recorded_model_identity_changed')
    for row in report['rows']:
        task_id,strategy=row['task_id'],row['strategy_id']
        if _json(row['score'])!=_json(tasks.judge(row['raw_output'],task_id)):raise ValueError('raw_score_changed')
        usage=row['usage']
        if (row['model']!=MODEL or row['response_status']!='generated_requires_review'
                or set(usage)!={'prompt_tokens','completion_tokens','total_tokens'}
                or any(type(v) is not int or v<0 for v in usage.values())
                or usage['completion_tokens']>128 or usage['total_tokens']!=usage['prompt_tokens']+usage['completion_tokens']):
            raise ValueError('recorded_usage_or_model_changed')
        request=MemoryRequest(MemoryScope(SCOPE.tenant_id,SCOPE.agent_id,'facts-'+task_id),tasks.TASKS[task_id]['query'],limit=20)
        selected=gateway.retrieve(reader,request)
        if selected.source_digest!=row['source_digest'] or [r.memory_id for r in selected.records]!=row['evidence_ids']:
            raise ValueError('evidence_changed_on_resume')
        if sorted((r.source_id,r.content) for r in selected.records)!=sorted((f['source_id'],f['content']) for f in tasks.TASKS[task_id]['evidence']):
            raise ValueError('registered_evidence_changed')
        with sqlite3.connect(gateway.ledger.path) as db:
            utility=db.execute('SELECT memory,revision,status,success,payload_hash FROM memory_utility WHERE tenant=? AND agent=? AND episode=?',
                              (SCOPE.tenant_id,SCOPE.agent_id,row['episode_id'])).fetchone()
            task={'task_id':task_id,'strategy_id':strategy}
            if utility != (report['strategy_ids'][strategy],REVISION,'judged',int(row['score']['strict_correct']),_hash(task)):
                raise ValueError('persistent_feedback_changed')
            claim=db.execute('SELECT task_hash,status,success,memory FROM memory_automatic_episodes_v1 WHERE tenant=? AND agent=? AND episode=?',
                             (SCOPE.tenant_id,SCOPE.agent_id,row['episode_id'])).fetchone()
            if claim!=(_hash(task),'judged',int(row['score']['strict_correct']),report['strategy_ids'][strategy]):
                raise ValueError('persistent_episode_claim_changed')
    trailing=0
    for row in reversed(report['rows']):
        if row['score']['strict_correct']:break
        trailing+=1
    if runner.status()!=dict(consumed=8,failures=trailing,stop_reason='episode_budget',max_episodes=8,max_failures=8):
        raise ValueError('run_claims_changed')
    with sqlite3.connect(gateway.ledger.path) as db:
        count=db.execute('SELECT COUNT(*) FROM memory_automatic_episodes_v1 WHERE tenant=? AND agent=? AND run=?',runner.key).fetchone()[0]
        if count!=8:raise ValueError('run_episode_roster_changed')


def _summary(rows):
    summary=[]
    for strategy in tasks.STRATEGIES:
        selected=[row for row in rows if row['strategy_id']==strategy]
        summary.append(dict(strategy=strategy,calls=len(selected),
            strict_correct=sum(row['score']['strict_correct'] for row in selected),
            supported_correct=sum(row['score']['strict_correct'] and tasks.TASKS[row['task_id']]['expected']!='ABSTAIN' for row in selected),
            abstention_correct=sum(row['score']['strict_correct'] and tasks.TASKS[row['task_id']]['expected']=='ABSTAIN' for row in selected),
            format_failures=sum(row['score']['format_failure'] for row in selected),
            non_abstaining_contract_failures=sum(row['score']['non_abstaining_contract_failure'] for row in selected)))
    return {'strategies':summary,'always_abstain_control_correct_per_four_tasks':sum(tasks.judge('ABSTAIN',task)['strict_correct'] for task in tasks.TASKS),
        'always_abstain_control_model_calls':0,'scope':'Training preference only; four unique tasks, eight matched calls. No causal superiority or validation claim.'}


def run(directory,expected_digest):
    if type(expected_digest) is not str or not re.fullmatch('[0-9a-f]{64}',expected_digest):
        raise ValueError('full_operator_pinned_model_digest_required')
    if len(tasks.TASKS)!=4 or len(tasks.STRATEGIES)!=2:raise ValueError('fixed_training_roster_required')
    root=Path(directory);root.mkdir(parents=True,exist_ok=True)
    path=root/'memory.sqlite'
    try:pins=sources()
    except BaseException:
        _quarantine(path)
        raise
    protocol=dict(version=REVISION,model=MODEL,origin=ORIGIN,expected_digest=expected_digest,
        dataset_sha256=_hash(tasks.TASKS),strategies=tasks.STRATEGIES,pairs=pairs(),source_sha256=pins,
        max_inference_calls=8,max_preload_calls=1,max_metadata_calls=2,max_output_tokens=128,
        socket_timeout_seconds=90,window=4,training_only=True)
    with _exclusive(root):
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS scientific_model_runs_v1(id INTEGER PRIMARY KEY,protocol TEXT,report TEXT,digest TEXT)')
            old=db.execute('SELECT protocol,report,digest FROM scientific_model_runs_v1 WHERE id=1').fetchone()
            if old is not None and old[0]!=_json(protocol):
                _quarantine(path)
                raise ValueError('frozen_scientific_protocol_changed')
            if old is None:db.execute('INSERT INTO scientific_model_runs_v1 VALUES(1,?,NULL,NULL)',(_json(protocol),))
        try:
            gateway,learning,proposer,reviewer,reader=_state(path)
            runner=ScientificLearningRun(learning,reader,path,REVISION,max_episodes=8,max_failures=8)
        except BaseException:
            _quarantine(path)
            raise
        if old is not None:
            try:
                if old[1] is None or sha256(old[1].encode()).hexdigest()!=old[2]:raise ValueError('interrupted_or_corrupt_training_claim')
                report=json.loads(old[1])
                if report['status']!='complete':raise ValueError('training_failed_or_interrupted_consumed')
                if _json(report['protocol'])!=_json(protocol):raise ValueError('recorded_protocol_changed')
                _validate_complete(gateway,learning,reader,runner,report)
            except BaseException:
                _quarantine(path)
                raise
            return report
        report=dict(protocol=protocol,status='running',rows=[],strategy_ids={},evidence={},
            inference_attempts=0,metadata_attempts=0,preload_attempts=0,training_only=True,
            validation_consumed=False,holdout_consumed=False,baseline_strategy='direct',
            model_weights_trained=False,persistent_kv_restored=False,promotion_authorized=False)
        _save(path,protocol,report)
        before=None;interrupted=None
        try:
            report['metadata_attempts']=1;_save(path,protocol,report)
            before=metadata();report['metadata_before']=before
            if before!={'model':MODEL,'digest':expected_digest}:raise ValueError('model_digest_mismatch')
            report['preload_attempts']=1;_save(path,protocol,report);report['preload']=preload()
            for strategy in tasks.STRATEGIES:
                mid=gateway.propose(proposer,scope=SCOPE,content=strategy,source_id='strategy-'+strategy)
                gateway.decide(reviewer,mid,scope=SCOPE,approve=True,evaluator_id='registered-strategy-v1')
                report['strategy_ids'][strategy]=mid
            for task_id,task in tasks.TASKS.items():
                scope=MemoryScope(SCOPE.tenant_id,SCOPE.agent_id,'facts-'+task_id)
                ids=[]
                for fact in task['evidence']:
                    mid=gateway.propose(proposer,scope=scope,content=fact['content'],source_id=fact['source_id'])
                    gateway.decide(reviewer,mid,scope=scope,approve=True,evaluator_id='synthetic-task-evidence-v1');ids.append(mid)
                selected=gateway.retrieve(reader,MemoryRequest(scope,task['query'],limit=20))
                if set(ids)!={r.memory_id for r in selected.records}:raise ValueError('all_registered_evidence_required')
                report['evidence'][task_id]={'ids':[r.memory_id for r in selected.records],'digest':selected.source_digest}
            for index,(task_id,strategy) in enumerate(pairs()):
                if sources()!=protocol['source_sha256']:raise ValueError('source_code_changed')
                report['inference_attempts']+=1;_save(path,protocol,report)
                request=MemoryRequest(MemoryScope(SCOPE.tenant_id,SCOPE.agent_id,'facts-'+task_id),tasks.TASKS[task_id]['query'],limit=20)
                row=runner.execute_pair(f'science-{index}',task_id,strategy,report['strategy_ids'][strategy],request,report['evidence'][task_id])
                report['rows'].append(row);_save(path,protocol,report)
            report['ranking']=_ranking(learning,reader,report['strategy_ids'])
            report['summary']=_summary(report['rows'])
            report['status']='awaiting_identity_check'
        except BaseException as exc:
            report['status']='failed_consumed';report['failure']=type(exc).__name__
            if not isinstance(exc,Exception):interrupted=exc
        finally:
            if before is not None:
                report['metadata_attempts']+=1;_save(path,protocol,report)
                try:
                    after=metadata();report['metadata_after']=after
                    if after!=before:raise ValueError('model_identity_changed')
                except BaseException as exc:
                    report['status']='failed_consumed';report['failure']=type(exc).__name__
                    if not isinstance(exc,Exception):interrupted=exc
            try:
                if sources()!=protocol['source_sha256']:raise ValueError('source_code_changed')
            except BaseException as exc:
                report['status']='failed_consumed';report['failure']='source_code_changed'
                if not isinstance(exc,Exception):interrupted=exc
            if report['status']=='awaiting_identity_check':
                report['status']='complete'
                try:_validate_complete(gateway,learning,reader,runner,report)
                except BaseException as exc:
                    report['status']='failed_consumed';report['failure']=type(exc).__name__
                    if not isinstance(exc,Exception):interrupted=exc
            if report['status']=='failed_consumed':
                _quarantine(path)
                report['feedback_invalidated']=True
            _save(path,protocol,report)
        if interrupted is not None:raise interrupted
        return report
