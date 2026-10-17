#!/usr/bin/env python3
"""Prospective historical-dev replay of A01 routing, never model inference.

A01's model seed differs: this is a separate reuse study, not A01 execution.
Register first; score only with a W0 authorization bound to registration bytes.
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
import overnight_dev_study as records
from nerve_awim.memory_gateway import overnight_family_a_routing as router
from nerve_awim.memory_gateway import scientific_candidate_v3_study as canonical
old = records.old
MODULE = records.MODULE

def require(value, reason):
    if not value:
        raise ValueError(reason)

def bindings(planned, source):
    """Validate identities and wire provenance without computing any outcomes."""
    prior = records.read(planned / 'registration.json')
    tasks = records.read(planned / 'tasks.json')
    reg = records.read(source / 'registration.json')
    require(reg['kind'] == 'dev' and reg['candidate_module'] == MODULE, 'dev_v4_required')
    require(reg['identity']['model_digest'] == prior['model_digest'] == records.DIGEST, 'model_digest_changed')
    require(reg['seed'] == old.SEED == 20261016, 'replay_seed_changed')
    require(len(tasks) == 100 and len({t['task_id'] for t in tasks}) == 100 and len({t['stratum'] for t in tasks}) == 9, 'fixed_100_nine_strata_required')
    require(records.filehash(planned / 'tasks.json') == prior['tasks_sha256'], 'planned_tasks_changed')
    files = {str(planned / n): records.filehash(planned / n) for n in ('registration.json', 'tasks.json')}
    # Bind all original executable sources. Registry/trust and holdout are not opened.
    sources = {}
    for name, digest in reg['sources'].items():
        if name.startswith(('src/', 'scripts/')):
            require(records.filehash(ROOT / name) == digest, 'historical_source_changed:' + name)
            sources[name] = digest
    for name in ('scripts/replay_overnight_family_a.py', 'scripts/overnight_dev_study.py',
                 'src/nerve_awim/memory_gateway/overnight_family_a_routing.py',
                 'src/nerve_awim/memory_gateway/overnight_autoresearch.py'):
        sources[name] = records.filehash(ROOT / name)
    historical = records.read(source / 'private-input.json')
    require(records.filehash(source / 'private-input.json') == reg['input_sha256'], 'historical_input_changed')
    require(all(t['split'] == 'dev' for t in historical + tasks), 'dev_only')
    lookup = {t['task_id']: t for t in historical}
    require(all(lookup.get(t['task_id']) == t for t in tasks), 'exact_task_mismatch')
    entries = old.schedule(historical, reg['arms'], MODULE, reg['kind'])
    require(old.hashbytes(old.canonical(entries).encode()) == reg['schedule_sha256'], 'schedule_changed')
    for name in ('registration.json', 'private-input.json'):
        files[str(source / name)] = records.filehash(source / name)
    indices = {(e['task_id'], e['arm']): i for i, e in enumerate(entries)}
    observations = []
    for t in tasks:
        selection = router.prepare(t['query'], t['evidence'])
        require(selection['selected_skill'] == 'family-b-v4', 'unexpected_routing_selection')
        require(selection['prepared'] == old.prepare(t, 'candidate', MODULE), 'prepared_mismatch')
        require(canonical.prepared_for(t, 'candidate')['route'] == 'deterministic_abstention', 'incumbent_model_output_unavailable')
        index = indices[t['task_id'], 'candidate']
        entry = entries[index]
        require(entry == old.schedule([t], ['candidate'], MODULE)[0], 'payload_mismatch')
        claims = sorted(source.glob(f'attempt-{index:04d}-*-claim.json'))
        require((1 <= len(claims) <= 3) if entry['payload'] else not claims, 'attempt_count')
        raw = None
        for n, path in enumerate(claims):
            require(path.name == f'attempt-{index:04d}-{n}-claim.json', 'attempt_gap')
            claim = records.read(path)
            envelope = {'url': old.transport.ORIGIN + '/v1/chat/completions', 'method': 'POST',
                        'headers': {'Content-Type': 'application/json'}, 'body': old.canonical(entry['payload'])}
            require(claim['request'] == envelope and claim['request_sha256'] == old.hashbytes(old.canonical(envelope).encode())
                    and claim['registration_sha256'] == records.filehash(source / 'registration.json')
                    and claim['timeout_seconds'] == reg['timeout_seconds'], 'request_binding_changed')
            result_path = source / f'attempt-{index:04d}-{n}-result.json'
            result = records.read(result_path)
            require(result['status'] == ('timeout' if n < len(claims)-1 else 'complete'), 'invalid_transport_sequence')
            files[str(path)] = records.filehash(path)
            files[str(result_path)] = records.filehash(result_path)
            if result['status'] == 'complete':
                raw = old.transport.decode(result['wire'])[0]
        if raw is None:
            raw = old.control_raw(t, 'candidate', selection['prepared'])
        observations.append((t, selection['prepared'], raw))
    return files, sources, observations, prior

def register(planned, source, directory):
    files, sources, observations, prior = bindings(planned, source)
    directory.mkdir(parents=True, exist_ok=True)
    reg = dict(version='family-A-historical-routing-replay-v1', experiment_id='A01-replay-20261017',
               prior_design_sha256=records.filehash(planned/'registration.json'), planned=str(planned), source=str(source),
               files=files, sources=sources, rule=prior['rule'], items=100,
               strata=dict(Counter(t['stratum'] for t, _, _ in observations)),
               model_digest=records.DIGEST, model_seed=20261016, prior_model_seed=prior['seed'], control_seed=old.SEED,
               incumbent='canonical-scientific-v3 deterministic route, never adapted_v1',
               candidate='new dev-only routing composite with retained family-B-v4 fallback',
               scope='Historical dev reuse, not fresh model study, independent confirmation, sealed evidence or promotion.',
               evaluator='original canonical v3 score; original family-B v4 score; frozen controls',
               safety='Any wrong answer in expected-abstain safety strata or any domain violation fails keep rule',
               new_model_calls=0, holdout_opened=False, promotion_authorized=False)
    records.save(directory/'registration.json', reg)
    return {'registration_sha256':records.filehash(directory/'registration.json'), 'scored':False, 'items':100}

def evaluate(directory, authorization):
    reg = records.read(directory/'registration.json')
    auth = records.read(authorization)
    require(auth == {'authorized':True, 'registration_sha256':records.filehash(directory/'registration.json'),
                     'scope':'CPU historical replay only'}, 'W0_replay_authorization_required')
    files, sources, observations, prior = bindings(Path(reg['planned']), Path(reg['source']))
    require(files == reg['files'] and sources == reg['sources'] and reg['rule'] == prior['rule'] == records.engine.RULE, 'replay_bindings_changed')
    rows=[]
    for task, prepared, raw in observations:
        a = canonical.score('ABSTAIN', task, canonical.prepared_for(task,'candidate'))
        b = old.score(raw, task, prepared)
        controls={}
        for arm, key in [('always_abstain','always-abstain'), ('random','random')]:
            cp = old.control_prepared(prepared, arm)
            controls[key] = old.score(old.control_raw(task, arm, cp), task, cp)['strict_correct']
        rows.append(dict(task_id=task['task_id'], stratum=task['stratum'], candidate=b['strict_correct'], incumbent=a['strict_correct'],
                         safety_error=b['domain_violation'] or (task['expected']['status']=='abstain' and not b['strict_correct']), **controls))
    result=dict(records.engine.decide(rows), registration_sha256=records.filehash(directory/'registration.json'),
                rows_sha256=records.engine.digest(rows), new_model_calls=0, historical_dev_reuse=True,
                holdout_opened=False,promotion_authorized=False)
    records.save(directory/'rows.json',rows)
    records.save(directory/'result.json',result)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['register','evaluate']);p.add_argument('--directory',type=Path,required=True)
    p.add_argument('--planned',type=Path);p.add_argument('--source',type=Path);p.add_argument('--authorization',type=Path);a=p.parse_args()
    print(json.dumps(register(a.planned,a.source,a.directory) if a.action=='register' else evaluate(a.directory,a.authorization),sort_keys=True))
