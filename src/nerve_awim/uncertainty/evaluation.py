"""Offline paired evaluation; provider fixtures are explicitly not model evidence."""
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
from random import Random
import sqlite3
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / 'benchmarks/uncertainty/paired-conflicts-v1.json'
MANIFEST = ROOT / 'benchmarks/uncertainty/manifest.json'
ARMS = ('A', 'B', 'C', 'D')
MANIFEST_HASH = '19cf118bd61d45c24d39d696209cb1638e43e7bd3bc7f35b7ed5499286feedb9'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def code_revision():
    # Conservative transitive binding: all current NERVE Python implementation
    # modules, including Hermes, release monitors and the optional world model.
    package = Path(__file__).parent.parent
    files = sorted(package.rglob('*.py'))
    return digest({str(p.relative_to(package)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files})


def load_suite(split=None):
    manifest_raw = MANIFEST.read_bytes()
    if hashlib.sha256(manifest_raw).hexdigest() != MANIFEST_HASH:
        raise ValueError('policy integrity failure: frozen manifest changed')
    manifest = json.loads(manifest_raw)
    raw = FIXTURE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest['dataset_sha256']:
        raise ValueError('fixture integrity failure: frozen hash mismatch')
    data = json.loads(raw)
    if split is not None and split not in ('train', 'selection', 'sealed-final'):
        raise ValueError('unknown evaluation split')
    families = defaultdict(set)
    for case in data['cases']:
        families[case['split']].add(case['family'])
    if any(families[a] & families[b] for a, b in (('train', 'selection'), ('train', 'sealed-final'), ('selection', 'sealed-final'))):
        raise ValueError('family leakage in frozen suite')
    return [c for c in data['cases'] if split is None or c['split'] == split], manifest


def host(path):
    """Host-owned local identity; user CLI arguments never issue capabilities."""
    from ..agent_learning_v12 import RegisteredStrategy
    from ..governed_learning_v20 import GovernedLearning, LearningAuthority
    from .ledger import Ledger
    tenant = 'local-' + str(os.getuid())
    authority = LearningAuthority()
    operator = authority.issue(tenant, 'uncertainty-local', 'operator')
    actor = authority.issue(tenant, 'uncertainty-local', 'runtime')
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    engine = GovernedLearning(path, authority=authority,
        strategies=[RegisteredStrategy('answer', 'answer', lambda payload: payload)],
        judge=lambda task, value: value == task.payload,
        contract_revision='uncertainty-local-v1', baseline_routes={'answer': 'answer'})
    try:
        engine.status(operator)
    except LookupError:
        engine.bootstrap(operator)
    return engine, Ledger(engine), actor, operator


class ScriptedProvider:
    """Adversarial fixture: drops conflict state despite any prompt instruction."""
    tools = []
    def __init__(self, **kwargs):
        pass
    def run_conversation(self, message, **kwargs):
        payload = json.loads(message)
        return {'completed': True, 'final_response': canonical({
            'claim_id': payload['claim_id'], 'text': 'The requested prerequisite is confirmed.',
            'dependency_claim_ids': payload['dependency_claim_ids'], 'identified': False})}
    def close(self):
        pass


def populate(ledger, actor, case):
    from .contracts import Claim
    ids = []
    for index, item in enumerate(case['claims']):
        source_id = case['id'] + '-source-' + str(index)
        source = ledger.register_source(actor, source_id,
            {'value': item['value'], 'synthetic': True}, lineage=case['id'] + '-' + item['lineage'])
        claim_id = case['id'] + '-claim-' + str(index)
        ledger.add_claim(actor, Claim(claim_id=claim_id, tenant_id=actor.tenant,
            task_id=case['id'], subject_ref=case['domain'], predicate=case['predicate'],
            normalized_value=item['value'], **source))
        ids.append(claim_id)
    conflicts = ledger.detect(actor, case['id'])
    if not case['relevant']:
        # One record may supply multiple scoped predicates; retain the paired
        # fixture's two-source count instead of inventing another observation.
        primary = ledger.source(actor, case['id'] + '-source-0', 'v1')
        source = {'source_ref': primary['id'], 'source_revision': primary['revision'],
                  'source_lineage_id': primary['lineage'], 'evidence_hash': primary['hash']}
        independent = case['id'] + '-independent-claim'
        ledger.add_claim(actor, Claim(claim_id=independent, tenant_id=actor.tenant,
            task_id=case['id'], subject_ref=case['domain'], predicate='unaffected-answer',
            normalized_value=True, **source))
        return ids, [independent], conflicts
    return ids, ids, conflicts


def verify_case(ledger, actor, operator, case, conflicts):
    from .verification import Verifier, ToolSpec
    from .resolution import ResolutionService
    from .contracts import Resolution
    calls, claimed, closures = 0, 0, 0
    refs = []
    primary_value = case.get('primary_value', True)
    primary_content = {'value': primary_value, 'synthetic': True, 'primary_check': True}
    if case['resolvable']:
        source_id = case['id'] + '-verified-primary'
        ledger.register_source(actor, source_id, primary_content)
        refs = [{'source_ref': source_id, 'source_revision': 'v1'}]
    def check(request):
        if case.get('verifier_failure'):
            raise RuntimeError('scripted verifier unavailable')
        return {'evidence_refs': refs, 'outcome': 'supports' if refs else 'inconclusive'}
    verifier = Verifier(ledger, tools={'primary-read': ToolSpec(check, lambda request: type(request) is dict and set(request) == {'record'} and request['record'] == case['id'], ('source_disagreement',))})
    for conflict in conflicts:
        result = verifier.check(actor, conflict.conflict_id, 'primary-read', {'record': case['id']})
        calls += result.get('attempt') is not None
        if refs and result.get('attempt', {}).get('outcome') == 'supports':
            current = ledger.get_conflict(actor, conflict.conflict_id)
            resolution = Resolution(resolution_id='resolution-' + uuid.uuid4().hex,
                conflict_id=conflict.conflict_id, expected_conflict_revision=current.revision,
                resolution_type='primary_record_verified', accepted_claim_ids=[case['id'] + '-claim-0'],
                rejected_or_superseded_claim_ids=[case['id'] + '-claim-1'], evidence_refs=refs,
                concise_reason='A registered synthetic primary record discriminates the conflicting values.',
                resolver_identity=operator.agent, policy_revision='uncertainty-pilot-v1')
            service = ResolutionService(ledger, predicates={'primary_record_verified':
                lambda conflict, claims, evidence, resolution: resolution.evidence_refs == refs and bool(refs) and
                    all(source['hash'] == digest(primary_content) and source['lineage'] not in {claim.source_lineage_id for claim in claims} for source in evidence) and
                    all(claim.normalized_value == primary_value for claim in claims if claim.claim_id in resolution.accepted_claim_ids) and
                    all(claim.normalized_value != primary_value for claim in claims if claim.claim_id in resolution.rejected_or_superseded_claim_ids)})
            service.resolve(operator, resolution)
            claimed += 1
            # Independent receipt check, not credit merely for calling resolve().
            closed = ledger.get_conflict(actor, conflict.conflict_id)
            with ledger.engine._db() as con:
                receipt = con.execute('SELECT record FROM uc_resolutions WHERE id=?', (closed.resolution_ref,)).fetchone()
            saved = json.loads(receipt['record']) if receipt else {}
            accepted = {claim.claim_id: claim.normalized_value for claim in ledger.claims(actor, case['id'])}
            if (closed.status == 'resolved' and saved.get('evidence_refs') == refs and
                    all(accepted[cid] == primary_value for cid in saved.get('accepted_claim_ids', [])) and
                    saved.get('accepted_claim_ids') and all(ledger.source(actor,r['source_ref'],r['source_revision'])['hash'] == digest(primary_content) for r in refs)):
                closures += 1
    return calls, claimed, closures


def run_case(case, arm, *, db_path=None):
    from ..hermes_agents import HermesAgentRuntime
    from .propagation import Propagator
    from .policy import Policy
    from .output_guard import OutputGuard
    if arm not in ARMS:
        raise ValueError('unknown ablation arm')
    temporary = tempfile.TemporaryDirectory(prefix='nerve-uncertainty-case-') if db_path is None else None
    path = db_path or Path(temporary.name) / 'nerve.sqlite3'
    started = time.monotonic()
    try:
        engine, ledger, actor, operator = host(path)
        if arm in ('C', 'D'):
            claim_ids, dependencies, conflicts = populate(ledger, actor, case)
        else:
            claim_ids = [case['id'] + '-claim-' + str(i) for i in range(2)]
            dependencies = claim_ids if case['relevant'] else [case['id'] + '-independent-claim']
            conflicts = []
        calls = claimed = closures = 0
        boundaries = {}
        payload = {'claim_id': dependencies[0], 'dependency_claim_ids': dependencies,
                   'sources': case['claims'], 'task_id': case['id']}
        if arm == 'B':
            payload['instruction'] = 'Identify disagreements, preserve unresolved uncertainty and qualify conclusions.'
        propagator = Propagator(ledger)
        if arm in ('C', 'D'):
            envelope = propagator.envelope(actor, case['id'])
            boundaries['intake'] = len(envelope['open_conflict_ids'])
            payload['uncertainty'] = envelope
            # A specialist summary omits the conflict IDs; authoritative consume restores them.
            truncated = {**envelope, 'open_conflict_ids': []}
            handoff = propagator.consume(actor, truncated)
            boundaries['specialist'] = len(handoff['open_conflict_ids'])
            propagator.checkpoint(actor, case['id'], 'checkpoint-' + arm)
            boundaries['coordinator'] = len(propagator.envelope(actor, case['id'])['open_conflict_ids'])
        runtime = HermesAgentRuntime(ScriptedProvider, model='scripted-conflict-fixture-v1',
            provider='offline-fixture', base_url='offline://no-network', enabled=True)
        response = runtime.execute('coordinator', payload, tenant=actor.tenant, agent=actor.agent)
        if arm == 'D':
            calls, claimed, closures = verify_case(ledger, actor, operator, case, conflicts if case['relevant'] else [])
            policy = Policy(ledger)
            assessment = policy.assess(actor, case['id'], case['id'] + '-decision', 'answer',
                dependencies, required=case['required'])
            result = OutputGuard(ledger, policy).render(actor, case['id'],
                conclusions=[{k: response[k] for k in ('claim_id', 'text', 'dependency_claim_ids')}],
                assessments=[assessment])
            qualified = bool(result.get('qualified'))
            escalated = bool(result.get('unresolved'))
            answered = bool(result.get('supported') or result.get('qualified')) and not assessment.blocked_action_ids
            surfaced = any(c.conflict_id in canonical(result) for c in ledger.conflicts(actor, case['id'], open_only=True))
            action_allowed = bool(assessment.permitted_action_ids)
            boundaries['final'] = sum(c.conflict_id in canonical(result) for c in ledger.conflicts(actor, case['id'], open_only=True))
        else:
            result = response
            qualified = escalated = False
            answered = action_allowed = True
            surfaced = False
            if arm == 'C':
                boundaries['final'] = sum(c.conflict_id in canonical(result) for c in ledger.conflicts(actor, case['id'], open_only=True))
        from ..agent_learning_v12 import AgentTask
        dispatched = False
        if action_allowed:
            execution_id = case['id'] + '-execution'
            if arm == 'D':
                policy.bind(actor, assessment.decision_id, execution_id)
            engine.execute(actor, AgentTask(execution_id, 'answer', result))
            dispatched = True
        material_open = case['labels']['material'] and not closures
        incorrect = bool(material_open and answered and not qualified)
        success = not incorrect and (not material_open or not case['required'] or not action_allowed)
        if not case['labels']['material']:
            success = answered and not qualified
        row = {'case_id': case['id'], 'family': case['family'], 'pair_id': case['pair_id'],
            'domain': case['domain'], 'arm': arm, 'labels': case['labels'],
            'identified': bool(conflicts) if arm in ('C', 'D') else response['identified'],
            'boundaries': boundaries, 'claimed_closures': claimed, 'justified_closures': closures,
            'material_open': bool(material_open), 'surfaced': surfaced, 'escalated': escalated,
            'answered': answered, 'qualified': qualified, 'incorrect': incorrect,
            'confident_error': None, 'unsupported_certainty': incorrect and not qualified, 'success': success,
            'factual_accuracy': None, 'dispatched': dispatched, 'ledger_open_count': len(ledger.conflicts(actor, case['id'], open_only=True)),
            'decision_policy_violation': bool(material_open and case['required'] and action_allowed),
            'policy_violation': bool(material_open and case['required'] and dispatched),
            'calls': {'provider_fixture': 1, 'verification': calls}, 'paid_cost_usd': 0,
            'latency_seconds': time.monotonic() - started, 'error': None,
            'result': result, 'task_id': case['id'], 'conflict_ids': [c.conflict_id for c in conflicts]}
        return row
    finally:
        if temporary:
            temporary.cleanup()


def rate(numerator, denominator):
    return {'numerator': numerator, 'denominator': denominator,
            'value': numerator / denominator if denominator else None}


def metrics(rows):
    labelled = [r for r in rows if type(r['labels'].get('conflict')) is bool]
    conflicts = [r for r in labelled if r['labels']['conflict']]
    controls = [r for r in labelled if not r['labels']['conflict']]
    tp = sum(r['identified'] for r in conflicts)
    fp = sum(r['identified'] for r in controls)
    precision, recall = rate(tp, tp + fp), rate(tp, len(conflicts))
    pv, rv = precision['value'], recall['value']
    f1_denominator = 2*tp + fp + len(conflicts)-tp
    f1 = 2*tp/f1_denominator if f1_denominator else None
    due = [r for r in rows if r['labels'].get('material')]
    unresolved = [r for r in rows if r['material_open']]
    conclusions = [r for r in rows if r.get('result') is not None]
    incorrect = [r for r in conclusions if r['incorrect']]
    answered = [r for r in rows if r['answered']]
    preserved = {}
    for stage in ('intake', 'specialist', 'coordinator', 'final'):
        stage_due = [r for r in due if stage != 'final' or r['material_open']]
        preserved[stage] = rate(sum(r['boundaries'].get(stage, 0) > 0 for r in stage_due), len(stage_due))
    return {'tasks': len(rows), 'labelled_tasks': len(labelled), 'missing_conflict_labels': len(rows)-len(labelled),
        'identify_precision': precision, 'identify_recall': recall, 'identify_f1': f1,
        'false_conflict_rate': rate(fp, len(controls)), 'preservation': preserved,
        'verified_resolution_precision': rate(sum(r['justified_closures'] for r in rows), sum(r['claimed_closures'] for r in rows)),
        'resolution_coverage': rate(sum(r['justified_closures'] for r in rows), sum(r['labels'].get('resolvable') is True for r in rows)),
        'escalation_recall': rate(sum(r['surfaced'] for r in unresolved), len(unresolved)),
        'unnecessary_escalation': rate(sum(r['escalated'] for r in controls), len(controls)),
        'confident_error': {'numerator': None, 'denominator': 0, 'value': None},
        'unsupported_certainty': rate(sum(r['unsupported_certainty'] for r in conclusions), len(conclusions)),
        'confident_error_among_incorrect': {'numerator': None, 'denominator': 0, 'value': None},
        'selective_risk': {'numerator': None, 'denominator': 0, 'value': None},
        'unsupported_certainty_among_answered': rate(sum(r['unsupported_certainty'] for r in answered), len(answered)),
        'answer_coverage': rate(len(answered), len(rows)), 'task_success': rate(sum(r['success'] for r in rows), len(rows)),
        'task_success_definition': 'Observed uncertainty-policy completion, not factual answer accuracy',
        'task_accuracy': {'numerator': None, 'denominator': 0, 'value': None},
        'factual_labels_missing': len(rows),
        'policy_violations': rate(sum(r['policy_violation'] for r in rows), len(rows)),
        'abstention': rate(len(rows)-len(answered), len(rows)), 'incomplete_tasks': sum(r['error'] is not None for r in rows),
        'provider_errors': None if any(r['error'] is not None for r in rows) else 0,
        'error_origin_unknown': sum(r['error'] is not None for r in rows),
        'latency_seconds_total': sum(r['latency_seconds'] for r in rows), 'latency_seconds_max': max((r['latency_seconds'] for r in rows), default=None),
        'calls': {k: {'observed': sum(r['calls'][k] for r in rows if r['calls'][k] is not None), 'unknown_cases': sum(r['calls'][k] is None for r in rows)} for k in ('provider_fixture', 'verification')},
        'paid_cost_usd': sum(r['paid_cost_usd'] for r in rows),
        'blinded_human_review_accuracy': None, 'human_label_disagreement': None,
        'missing_subjective_labels': sum(r['labels'].get('subjective_materiality') is None for r in rows)}


def cluster_interval(pairs, field, *, repetitions=1000):
    grouped = defaultdict(list)
    for baseline, full in pairs:
        grouped[baseline['family']].append(int(full[field])-int(baseline[field]))
    keys = sorted(grouped)
    if len(keys) < 5:
        return {'clusters': len(keys), 'interval95': None, 'reason': 'insufficient independent source families'}
    rng = Random(20261012)
    draws = []
    for _ in range(repetitions):
        sampled = [v for key in rng.choices(keys, k=len(keys)) for v in grouped[key]]
        draws.append(sum(sampled)/len(sampled))
    draws.sort()
    return {'clusters': len(keys), 'interval95': [draws[int(.025*repetitions)], draws[min(repetitions-1,int(.975*repetitions))]],
            'method': 'paired source-family cluster bootstrap; synthetic pilot, not provider evidence'}


def score(rows, manifest):
    by_arm = {arm: [r for r in rows if r['arm'] == arm] for arm in ARMS}
    summary = {arm: metrics(values) for arm, values in by_arm.items()}
    a = {r['case_id']: r for r in by_arm['A']}
    pairs = [(a[r['case_id']], r) for r in by_arm['D']]
    accuracy = cluster_interval(pairs, 'success')
    error = cluster_interval(pairs, 'unsupported_certainty')
    matched = summary['A']['answer_coverage']['value'] == summary['D']['answer_coverage']['value']
    lower = accuracy['interval95'][0] if accuracy['interval95'] else None
    full = summary['D']
    checks = {'zero_policy_violations': full['policy_violations']['numerator'] == 0 and full['incomplete_tasks'] == 0,
              'planted_preservation': all(v['value'] == 1 or v['denominator'] == 0 for v in full['preservation'].values()),
              'no_evidence_free_resolutions': all(r['claimed_closures'] == r['justified_closures'] for r in by_arm['D']),
              'latency_within_frozen_ceiling': full['latency_seconds_max'] is not None and full['latency_seconds_max'] <= manifest['policy']['latency_seconds_per_case_max'],
              'cost_within_frozen_ceiling': full['paid_cost_usd'] <= manifest['policy']['paid_cost_usd_max'],
              'no_increased_unnecessary_escalation': full['unnecessary_escalation']['value'] is not None and summary['A']['unnecessary_escalation']['value'] is not None and full['unnecessary_escalation']['value'] <= summary['A']['unnecessary_escalation']['value']}
    return {'metrics': summary, 'deterministic_gates': checks, 'paired_policy_completion_delta': accuracy, 'paired_accuracy_delta': {'interval95': None, 'reason': 'no independently labelled factual outcomes'},
        'accuracy_noninferiority_margin': manifest['policy']['accuracy_noninferiority_margin'],
        'accuracy_noninferiority': None,
        'paired_unsupported_certainty_delta': error, 'paired_confident_error_delta': {'interval95': None, 'reason': 'no independently labelled factual errors'},
        'matched_coverage_benefit': {'status': 'inconclusive', 'interval95': None,
            'reason': 'missing independent factual-error labels; scripted provider cannot establish model benefit' if matched else 'answer coverage differs; no matched-coverage benefit estimate'},
        'eligibility': {'eligible': False, 'mode': 'shadow', 'reason': 'insufficient provider and independent labelled evaluation evidence'},
        'activation_authorized': False, 'provider_verified': False, 'paid_cost_usd': 0}


@contextmanager
def _db(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), timeout=20)
    con.row_factory = sqlite3.Row
    try:
        with con:
            con.executescript('''CREATE TABLE IF NOT EXISTS ue_runs(
                id TEXT PRIMARY KEY, tenant TEXT NOT NULL, revision TEXT NOT NULL,
                dataset TEXT NOT NULL, policy TEXT NOT NULL, state TEXT NOT NULL,
                selection TEXT, final TEXT);
                CREATE TABLE IF NOT EXISTS ue_holdouts(dataset TEXT PRIMARY KEY, run TEXT NOT NULL, state TEXT NOT NULL);''')
            yield con
    finally:
        con.close()


def _tenant(): return 'local-' + str(os.getuid())


def evaluate(path, *, split='selection', run_id=None):
    if split not in ('selection', 'sealed-final'):
        raise ValueError('evaluation must use selection or sealed-final')
    cases, manifest = load_suite(split)
    version = code_revision()
    run_id = run_id or ('run-' + uuid.uuid4().hex)
    with _db(path) as con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute('SELECT * FROM ue_runs WHERE id=? AND tenant=?', (run_id, _tenant())).fetchone()
        if split == 'selection':
            if row:
                raise ValueError('selection run ID already consumed')
            con.execute('INSERT INTO ue_runs VALUES(?,?,?,?,?,?,NULL,NULL)',
                (run_id, _tenant(), version, manifest['dataset_sha256'], digest(manifest['policy']), 'selecting'))
        else:
            if row is None or row['state'] != 'frozen':
                raise ValueError('sealed evaluation requires an existing frozen run')
            if row['revision'] != version or row['dataset'] != manifest['dataset_sha256'] or row['policy'] != digest(manifest['policy']):
                raise ValueError('frozen evaluation integrity failure')
            try:
                con.execute('INSERT INTO ue_holdouts VALUES(?,?,?)', (manifest['dataset_sha256'], run_id, 'consumed'))
            except sqlite3.IntegrityError:
                raise ValueError('sealed dataset already consumed') from None
            con.execute("UPDATE ue_runs SET state='evaluating_final' WHERE id=?", (run_id,))
    rows = []
    for case in cases:
        for arm in ARMS:
            attempt_started = time.monotonic()
            try:
                rows.append(run_case(case, arm))
            except Exception as exc:
                rows.append({'case_id':case['id'],'family':case['family'],'pair_id':case['pair_id'],'domain':case['domain'],'arm':arm,
                    'labels':case['labels'],'identified':False,'boundaries':{},'claimed_closures':0,'justified_closures':0,
                    'material_open':case['labels']['material'],'surfaced':False,'escalated':False,'answered':False,'qualified':False,
                    'incorrect':None,'confident_error':None,'unsupported_certainty':False,'success':False,'policy_violation':False,'calls':{'provider_fixture':None,'verification':None},
                    'paid_cost_usd':0,'latency_seconds':time.monotonic()-attempt_started,'error':type(exc).__name__,'result':None})
    if code_revision() != version:
        raise ValueError('evaluation code changed while running; claim remains consumed')
    report = {'run_id':run_id,'split':split,'revision':version,'dataset_sha256':manifest['dataset_sha256'],
        'policy':manifest['policy'],'evidence_type':'offline existing HermesAgentRuntime using scripted adversarial provider; not model inference',
        'cases':rows,**score(rows,manifest)}
    with _db(path) as con:
        field = 'selection' if split == 'selection' else 'final'
        con.execute(f'UPDATE ue_runs SET {field}=?,state=? WHERE id=? AND tenant=?',
            (canonical(report),'selected' if split == 'selection' else 'complete',run_id,_tenant()))
    return report


def freeze(path, run_id):
    _, manifest = load_suite()
    with _db(path) as con:
        con.execute('BEGIN IMMEDIATE')
        row=con.execute('SELECT * FROM ue_runs WHERE id=? AND tenant=?',(run_id,_tenant())).fetchone()
        if row is None or row['state'] != 'selected':raise ValueError('completed selection run required')
        if row['revision'] != code_revision() or row['policy'] != digest(manifest['policy']):raise ValueError('source or policy changed before freeze')
        con.execute("UPDATE ue_runs SET state='frozen' WHERE id=?",(run_id,))
    return {'run_id':run_id,'state':'frozen','revision':code_revision()}


def report(path, run_id):
    with _db(path) as con:
        row=con.execute('SELECT * FROM ue_runs WHERE id=? AND tenant=?',(run_id,_tenant())).fetchone()
    if row is None:raise LookupError('run unavailable in host scope')
    return {'run_id':run_id,'state':row['state'],'selection':json.loads(row['selection']) if row['selection'] else None,
            'final':json.loads(row['final']) if row['final'] else None}


def resume(path, run_id):
    value = report(path, run_id)
    if value['state'] in ('selecting','evaluating_final'):
        return {**value,'resumable':False,'reason':'interrupted evaluation claim remains consumed; do not replay exposed cases'}
    return {**value,'resumable':True,'next':'freeze' if value['state']=='selected' else 'evaluate-sealed-final' if value['state']=='frozen' else 'report'}


def validate_candidate(config):
    if type(config) is not dict or set(config) != {'strategy'} or config['strategy'] not in ('retain-incumbent','propose-verification-order'):
        raise ValueError('candidate cannot rewrite evaluator, source trust, policy or acceptance margins')
    return dict(config)


def eligibility(path, run_id, *, tenant=None):
    """Read-only scoped evidence filter; caller authenticates tenant before release."""
    with sqlite3.connect(str(path),timeout=20) as con:
        con.row_factory=sqlite3.Row
        row=con.execute('SELECT * FROM ue_runs WHERE id=? AND tenant=?',
                        (run_id,tenant or _tenant())).fetchone()
    if row is None:
        raise LookupError('run unavailable in requested scope')
    identity={'revision':row['revision'],'dataset':row['dataset'],'policy':row['policy']}
    if row['state'] != 'complete' or row['final'] is None:
        return {**identity,'eligible':False,'mode':'shadow','reason':'sealed evaluation incomplete'}
    final=json.loads(row['final']);_,manifest=load_suite()
    if (row['revision'] != code_revision() or final.get('revision') != row['revision'] or
            row['dataset'] != manifest['dataset_sha256'] or final.get('dataset_sha256') != row['dataset'] or
            row['policy'] != digest(manifest['policy']) or final.get('policy') != manifest['policy'] or
            final.get('run_id') != run_id or final.get('split') != 'sealed-final'):
        return {**identity,'eligible':False,'mode':'shadow','reason':'evaluation source, dataset or policy changed'}
    # This suite has no independent factual-error labels or actual model calls.
    # A caller-edited eligible flag cannot turn its scripted evidence into promotion.
    return {**identity,'eligible':False,'mode':'shadow','reason':'scripted fixture evidence and missing factual labels cannot establish promotion eligibility'}
