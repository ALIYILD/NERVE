"""Trusted compiler for exact normalized transitions, never generated Python."""
from .contracts import Rule, canonical, digest, exact, observation, REVISION


def compile_rules(rules, *, backend="declarative-exact-v1"):
    if not 1 <= len(rules) <= 256:
        raise ValueError('one to 256 rules required')
    entries = []
    keys = set()
    ids = set()
    for raw in rules:
        rule = Rule.load(raw)
        if rule.status != 'supported' or rule.exceptions or rule.unresolved_alternatives:
            raise ValueError('only supported resolved rules compile')
        key = digest([rule.preconditions,rule.action])
        if key in keys or rule.rule_id in ids:
            raise ValueError('ambiguous or duplicate rules')
        keys.add(key)
        ids.add(rule.rule_id)
        entries.append({'rule_id':rule.rule_id,'before':rule.preconditions,
                        'action':rule.action,'after':rule.predicted_effect,'goal':rule.completion})
    program = {'revision':REVISION,'backend':backend,'entries':entries}
    canonical(program)
    return validate_program(program)


def validate_program(program):
    exact(program, ('revision','backend','entries'))
    if program['revision'] != REVISION or program['backend'] not in ('declarative-exact-v1','declarative-frame-v1'):
        raise ValueError('unsupported executable backend/revision')
    if type(program['entries']) is not list or not 1 <= len(program['entries']) <= 256:
        raise ValueError('bounded declarative entries required')
    seen = set()
    for entry in program['entries']:
        exact(entry, ('rule_id','before','action','after','goal'))
        from .contracts import identifier
        identifier(entry['rule_id'])
        identifier(entry['action'])
        for key in ('before','after'):
            if observation(entry[key]) is None:
                raise ValueError('known declarative states required')
        if entry['goal'] is not None and type(entry['goal']) is not bool:
            raise ValueError('invalid goal')
        if program['backend'] == 'declarative-frame-v1':
            from .generalization import validate_frame
            validate_frame(entry['before'],entry['after'])
        key = digest([entry['before'],entry['action']])
        if key in seen:
            raise ValueError('ambiguous executable')
        seen.add(key)
    return program


class Simulator:
    """Pure trusted interpreter of bounded data; unsupported mechanics are unknown.

    State is rebuilt from each episode's initial observation. This v1 exact-state
    contract deliberately does not infer hidden state from a partial observation.
    """
    def __init__(self, program):
        self.program = validate_program(program)

    def initialise(self, initial_observation):
        observation(initial_observation)
        return {'observation':initial_observation,'goal':None,'rule_id':None}

    def step(self, state, action):
        from .generalization import matches, apply
        candidates=[]
        for entry in self.program['entries']:
            known = (matches(entry['before'],state['observation'])
                     if self.program['backend'] == 'declarative-frame-v1'
                     else canonical(entry['before']) == canonical(state['observation']))
            if known and entry['action'] == action:
                candidates.append(entry)
        if len(candidates) == 1:
            entry=candidates[0]
            try:
                predicted=(apply(entry['after'],state['observation'])
                           if self.program['backend'] == 'declarative-frame-v1' else entry['after'])
            except ValueError:
                predicted=None
            return {'observation':predicted,'goal':entry['goal'] if predicted is not None else None,'rule_id':entry['rule_id']}
        return {'observation':None,'goal':None,'rule_id':None}

    def observe(self, state):
        return state['observation']

    def goal(self, state):
        return state['goal']
