"""Independent structural reviewer for the finite declarative language only.

Checks rule-to-executable correspondence; not a proof of environment fidelity.
It does not call the compiler, and cannot approve arbitrary generated code.
"""
from .contracts import Rule, canonical
from .compiler import validate_program


def assess(rules, program):
    validate_program(program)
    expected = {}
    for raw in rules:
        r = Rule.load(raw)
        if r.status != 'supported' or r.rule_id in expected or r.exceptions or r.unresolved_alternatives:
            return {'status':'disagree','reason':'unresolved_or_duplicate_rule'}
        expected[r.rule_id] = (r.preconditions,r.action,r.predicted_effect,r.completion)
    actual = {e['rule_id']:(e['before'],e['action'],e['after'],e['goal']) for e in program['entries']}
    passed = canonical({k:list(v) for k,v in expected.items()}) == canonical({k:list(v) for k,v in actual.items()}) and len(actual) == len(program['entries'])
    return {'status':'pass' if passed else 'disagree','reviewer':'independent-structural-v1',
            'scope':'finite exact-transition DSL; not a formal proof or provider review'}
