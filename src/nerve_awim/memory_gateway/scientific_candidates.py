"""Bounded, deterministic research proposals from scoped synthetic failures.

No model research agent, candidate execution, holdout access, promotion or
negative-evidence suppression is implemented here. Hypothesis registration is a
content-addressed record for a future durable selection gate, not approval.
"""
from hashlib import sha256
from pathlib import Path
import re
import json
import sqlite3
from .experience_store import _json, _hash

REVISION='scientific-candidates-v1'
CONFIG_FIELDS={'conflict_detection','prompt_template','retrieval_k','abstention_threshold','tool_rule'}
SPACE={
    'conflict_check':dict(conflict_detection=True,prompt_template='evidence_json_v1',retrieval_k=4,abstention_threshold='strict',tool_rule='evidence_only'),
    'format_contract':dict(conflict_detection=False,prompt_template='json_contract_first_v1',retrieval_k=4,abstention_threshold='strict',tool_rule='evidence_only'),
    'evidence_coverage':dict(conflict_detection=False,prompt_template='evidence_json_v1',retrieval_k=8,abstention_threshold='strict',tool_rule='evidence_only'),
    'abstention_check':dict(conflict_detection=False,prompt_template='evidence_json_v1',retrieval_k=4,abstention_threshold='strict_with_evidence_check',tool_rule='evidence_only'),
}
_REGISTERED_SPACE=_json(SPACE)
EFFECTS={
    'conflict_check':('Reduce non-abstaining outputs when current matching evidence conflicts.','multi-source-agreement'),
    'format_contract':('Reduce output-contract failures without changing evidence authority.','supported-measurement'),
    'evidence_coverage':('Reduce missed supporting evidence through a bounded larger retrieval set.','entity-decoy'),
    'abstention_check':('Reduce incorrect selections through an explicit evidence sufficiency check.','supported-measurement'),
}


def sources():
    root=Path(__file__).resolve().parents[3]
    names=('src/nerve_awim/memory_gateway/scientific_candidates.py',
           'src/nerve_awim/memory_gateway/experience_store.py')
    return {name:sha256((root/name).read_bytes()).hexdigest() for name in names}


def validate_config(config):
    if _json(SPACE)!=_REGISTERED_SPACE:raise ValueError('mutation_registry_changed')
    if (type(config) is not dict or set(config)!=CONFIG_FIELDS
            or type(config['conflict_detection']) is not bool
            or type(config['retrieval_k']) is not int or config['retrieval_k'] not in (4,8)
            or config['prompt_template'] not in ('evidence_json_v1','json_contract_first_v1')
            or config['abstention_threshold'] not in ('strict','strict_with_evidence_check')
            or config['tool_rule']!='evidence_only'):
        raise ValueError('bounded_typed_candidate_required')
    if _json(config) not in {_json(c) for c in SPACE.values()}:
        raise ValueError('unregistered_configuration_combination')
    return _hash(config)


def _clusters(episodes):
    groups={}
    for episode in episodes:
        if episode['failure_class']=='none':continue
        key=(episode['stratum'],episode['failure_class'])
        groups.setdefault(key,[]).append({'episode_id':episode['episode_id'],'payload_sha256':_hash(episode)})
    result=[]
    for (stratum,failure),members in sorted(groups.items()):
        body=dict(stratum=stratum,failure_class=failure,members=sorted(members,key=lambda m:m['episode_id']))
        result.append(dict(**body,cluster_sha256=_hash(body)))
    return result


def _mutation(failure):
    return ('conflict_check' if failure=='conflict_non_abstaining' else
            'format_contract' if failure=='format_failure' else
            'evidence_coverage' if failure=='supported_abstention' else 'abstention_check')


def register_hypothesis(config,cluster,*,store_head,mode):
    """Construct a hash-bound proposal; authoritative validation is separate."""
    candidate_hash=validate_config(config)
    if mode not in ('deterministic_failure_rules','enumeration_fallback'):raise ValueError('registered_proposal_mode_required')
    if type(store_head) is not str or not re.fullmatch('[0-9a-f]{64}',store_head):raise ValueError('store_head_required')
    if type(cluster) is not dict or set(cluster)!={'stratum','failure_class','members','cluster_sha256'}:
        raise ValueError('registered_cluster_required')
    if (not cluster['members'] or len(cluster['members'])>10000
            or cluster['cluster_sha256']!=_hash({k:v for k,v in cluster.items() if k!='cluster_sha256'})):
        raise ValueError('cluster_binding_changed')
    mutation=next(name for name,value in SPACE.items() if _json(value)==_json(config))
    effect,risk=EFFECTS[mutation]
    body=dict(version=REVISION,candidate=dict(config),candidate_sha256=candidate_hash,
        hypothesis=dict(cluster=cluster,mutation=mutation,predicted_effect=effect,risk_stratum=risk),
        mode=mode,store_head=store_head,source_sha256=sources(),
        model_calls=0,holdout_accessed=False,promotion_authorized=False)
    # JSON round-trip makes caller mutations unable to change this returned record.
    return json.loads(_json(dict(**body,hypothesis_sha256=_hash(body))))


def validate_hypothesis(record,store,actor):
    """Recheck exact hash, rules and authoritative current scoped cluster evidence."""
    if type(record) is not dict:raise ValueError('registered_hypothesis_required')
    try:
        cluster=record['hypothesis']['cluster']
        if (record['mode']=='deterministic_failure_rules'
                and record['hypothesis']['mutation']!=_mutation(cluster['failure_class'])):
            raise ValueError('failure_mutation_mapping_changed')
        expected=register_hypothesis(record['candidate'],cluster,store_head=record['store_head'],mode=record['mode'])
        if _json(expected)!=_json(record):raise ValueError('hypothesis_changed')
        result=store.query(actor)
        if result['status']!='live' or result['head']!=record['store_head'] or cluster not in _clusters(result['episodes']):
            raise ValueError('authoritative_cluster_changed')
    except (KeyError,TypeError,StopIteration) as error:raise ValueError('registered_hypothesis_required') from error
    return True


def propose(store,actor,*,research_agent_enabled=True,max_proposals=4):
    if type(research_agent_enabled) is not bool or type(max_proposals) is not int or not 1<=max_proposals<=4:
        raise ValueError('bounded_proposal_configuration_required')
    mode='deterministic_failure_rules' if research_agent_enabled else 'enumeration_fallback'
    try:
        result=store.query(actor)
    except PermissionError:
        raise
    except (ValueError,sqlite3.Error,OSError):
        result={'status':'degraded','reason':'integrity_failure'}
    report=dict(status=result['status'],mode=mode,model_research_agent=False,model_calls=0,
                holdout_accessed=False,promotion_authorized=False,negative_evidence_enforced=False,proposals=[])
    if result['status']!='live':
        report['reason']=result.get('reason','unavailable');return report
    clusters=_clusters(result['episodes'])
    if not clusters:
        report['reason']='no_failure_data';return report
    report.update(reason='proposed',store_head=result['head'],source_sha256=sources())
    if research_agent_enabled:
        choices=[]
        # Prioritize the measured conflict failure independently of caller hints.
        ordered=sorted(clusters,key=lambda c:(c['failure_class']!='conflict_non_abstaining',c['stratum'],c['failure_class']))
        for cluster in ordered:
            failure=cluster['failure_class']
            mutation=_mutation(failure)
            choices.append((mutation,cluster))
    else:
        choices=[(mutation,clusters[0]) for mutation in SPACE]
    seen=set()
    for mutation,cluster in choices:
        config=SPACE[mutation];candidate_hash=validate_config(config)
        if candidate_hash in seen:continue
        seen.add(candidate_hash)
        report['proposals'].append(register_hypothesis(config,cluster,store_head=result['head'],mode=mode))
        if len(report['proposals'])==max_proposals:break
    return report
