"""Training-only induction of bounded frame rules, with explicit schema guards.

Rules are hypotheses about operational transitions, not calibrated probabilities.
No environment code, final answers, expressions or arbitrary functions enter the
proposer. Every changed field must fit a whitelisted operation on every support.
"""
from copy import deepcopy
from .contracts import Rule, canonical, digest, exact, identifier

FRAME_BACKEND = 'declarative-frame-v1'
TYPES = {str:'string',bool:'boolean',int:'integer',float:'number',type(None):'null'}


def schema(value):
    if type(value) is not dict or not value or any(type(v) not in TYPES for v in value.values()):
        raise ValueError('frame language requires a nonempty flat scalar observation')
    canonical(value)
    return {k:TYPES[type(v)] for k,v in value.items()}


def validate_frame(before, effects):
    exact(before,('equals','schema'))
    if type(before['equals']) is not dict or type(before['schema']) is not dict or not before['schema']:
        raise ValueError('explicit frame guard and schema required')
    if not set(before['equals']) <= set(before['schema']) or any(v not in TYPES.values() for v in before['schema'].values()):
        raise ValueError('invalid schema guard')
    if any(TYPES.get(type(v)) != before['schema'][k] for k,v in before['equals'].items()):
        raise ValueError('guard value differs from declared type')
    if type(effects) is not dict or not effects or not set(effects) <= set(before['schema']):
        raise ValueError('bounded frame assignments required')
    for key,expression in effects.items():
        if type(expression) is not dict or 'op' not in expression:
            raise ValueError('structured assignment required')
        op=expression['op']
        if op == 'constant':
            exact(expression,('op','value'))
            if TYPES.get(type(expression['value'])) != before['schema'][key]:
                raise ValueError('assignment must preserve field type')
        elif op == 'add':
            exact(expression,('op','field','value'))
            if expression['field'] not in before['schema'] or before['schema'][key] != 'integer' or before['schema'][expression['field']] != 'integer':
                raise ValueError('integer addition only')
            if type(expression['value']) is not int or not -1000 <= expression['value'] <= 1000:
                raise ValueError('bounded integer delta required')
        elif op in ('copy','strip','lower','strip_lower'):
            exact(expression,('op','field'))
            source=expression['field']
            if source not in before['schema'] or before['schema'][source] != before['schema'][key]:
                raise ValueError('same-type source required')
            if op != 'copy' and before['schema'][source] != 'string':
                raise ValueError('string transform required')
        else:
            raise ValueError('unknown operation; expressions and arbitrary code forbidden')


def matches(before, observation):
    try:
        return schema(observation) == before['schema'] and all(canonical(observation[k]) == canonical(v) for k,v in before['equals'].items())
    except ValueError:
        return False


def apply(effects, observation):
    result=deepcopy(observation)
    for key,expression in effects.items():
        op=expression['op']
        value=expression.get('value') if op == 'constant' else observation[expression['field']]
        if op == 'add':
            value+=expression['value']
            if abs(value) > 2**53:
                raise ValueError('integer result out of normalized range')
        elif op == 'strip':
            value=value.strip()
        elif op == 'lower':
            value=value.lower()
        elif op == 'strip_lower':
            value=value.strip().lower()
        result[key]=value
    canonical(result)
    return result


def infer(episodes, *, retain_context=True):
    """Propose one conservative frame per family/action and goal label.

    At least two different observations per group are required. Unchanged fields
    are copied, never dropped from replay comparison. Conflicting groups remain
    unknown at execution (the interpreter requires a unique matching rule).
    """
    if any(ep['split'] != 'train' for ep in episodes):
        raise PermissionError('only training observations may enter induction')
    groups={}
    for ep in episodes:
        for row in ep['transitions']:
            if row['status'] != 'observed' or row['completion'] is None:
                continue
            try:
                before_schema=schema(row['previous'])
                if schema(row['outcome']) != before_schema:
                    continue
            except ValueError:
                continue
            key=(ep['family'],row['action'],canonical(before_schema),row['completion'])
            groups.setdefault(key,[]).append(row)
    rules=[]
    for (family,action,_,completion),rows in sorted(groups.items()):
        if len({digest(r['previous']) for r in rows}) < 2:
            continue
        first=rows[0]['previous']
        equals={k:v for k,v in first.items() if all(canonical(r['previous'][k]) == canonical(v) for r in rows)}
        if not retain_context:
            equals={k:v for k,v in equals.items() if k not in ('family','environment')}
        effects={}
        for field in first:
            if all(canonical(r['previous'][field]) == canonical(r['outcome'][field]) for r in rows):
                continue
            hypotheses=[]
            values=[r['outcome'][field] for r in rows]
            if all(canonical(v) == canonical(values[0]) for v in values):
                hypotheses.append({'op':'constant','value':values[0]})
            if type(first[field]) is int:
                delta=rows[0]['outcome'][field]-first[field]
                if type(delta) is int and -1000 <= delta <= 1000:
                    hypotheses.append({'op':'add','field':field,'value':delta})
            if type(first[field]) is str:
                hypotheses.extend({'op':op,'field':field} for op in ('strip','lower','strip_lower'))
            hypotheses.extend({'op':'copy','field':source} for source in first if source != field and type(first[source]) is type(first[field]))
            chosen=None
            for hypothesis in hypotheses:
                if all(canonical(apply({field:hypothesis},r['previous'])[field]) == canonical(r['outcome'][field]) for r in rows):
                    chosen=hypothesis
                    break
            if chosen is None:
                effects={}
                break
            effects[field]=chosen
        if not effects:
            continue
        before={'equals':equals,'schema':schema(first)}
        validate_frame(before,effects)
        rid='frame_'+digest([family,action,before,effects,completion])[:24]
        refs=[r['id'] for r in rows]
        contradictions=[r['id'] for r in rows if r['prediction'] is not None and canonical(r['prediction']) != canonical(r['outcome'])]
        rules.append(Rule(rid,1,family,before,action,effects,completion,refs,contradictions,status='supported').to_dict())
    return {'decision':'revise_rulebook' if rules else 'retain','failure_class':'observed_invariants' if rules else 'insufficient_diverse_evidence',
            'evidence':[i for r in rules for i in r['supporting_transition_ids']],
            'rules':rules,'provider':'deterministic training-only frame induction','backend':FRAME_BACKEND}
