"""Synthetic ARC + task adaptation + uncertainty + Memento integration receipt.

No model provider, network API, paid training or external actuation is used.
A fresh explicitly selected database is required; never overwrite existing state.
"""
import argparse
import json
from pathlib import Path


def run(state):
    path = Path(state)
    if path.exists() and path.stat().st_size:
        raise ValueError('combined demo requires a fresh state file; existing history is preserved')
    path.parent.mkdir(parents=True, exist_ok=True)
    from ..adaptation_replay import build, start, correction
    from .ledger import Ledger
    from .contracts import Claim
    from .policy import Policy
    from .propagation import Propagator
    from .output_guard import OutputGuard
    from .world_model_adapter import WorldModelUncertainty
    from ..world_model.ledger import Ledger as WorldLedger, migrate
    from ..world_model.demo import populate
    from ..world_model.reflection import reflect
    from ..world_model.compiler import compile_rules
    from ..world_model.registry import Registry
    from ..world_model.contracts import Policy as WorldPolicy

    clock = lambda: 100.0  # Explicit fixture clock, not a live observation timestamp.
    components = build(path, now=clock)
    actor, operator, engine, adaptation, arc = [components[k] for k in
        ('actor', 'operator', 'engine', 'adaptation', 'runtime')]
    start(components, task='combined', subject='synthetic-subject')
    ledger = Ledger(engine, clock=clock)
    policy = Policy(ledger, clock=clock)
    propagation = Propagator(ledger)

    def claim(ident, value, task='combined'):
        source = ledger.register_source(actor, 'source-' + ident, {'value': value, 'synthetic': True})
        record = Claim(ident, actor.tenant, task, 'synthetic-subject', 'required-source', value, **source)
        ledger.add_claim(actor, record)
        return record

    def step(heading, section, *, task='combined', dependencies=('claim-yes',), parent=None):
        decision = arc.propose(actor, task, 'note', {'heading': heading,
            'facts': 'synthetic-fact', 'section': section}, [], 'synthetic-goal',
            ['objective'], parent_decision_id=parent)
        assessment = policy.assess(actor, task, decision.decision_id, 'note', list(dependencies), required=True)
        policy.bind(actor, decision.decision_id)
        before = len(components['effects'])
        outcome = arc.execute(actor, decision.decision_id)
        return decision, assessment, {'decision_id': decision.decision_id,
            'semantic_status': outcome.semantic_status, 'transport_status': outcome.transport_status,
            'assessment_status': assessment.status, 'handler_effects': len(components['effects']) - before}

    claim('claim-yes', True)
    first, _, initial = step('wrong', 'initial')
    correction_id = correction(components, 'combined', first.decision_id, 'verified-heading')
    second, _, corrected = step('verified-heading', 'corrected', parent=first.decision_id)

    # Memento uses the SAME authority and SQLite store, with explicit migration.
    migrate(path)
    world = WorldLedger(path, components['authority'])
    world_guard = WorldModelUncertainty(ledger, world)
    world_guard.enable(operator, mode='enforce')
    trainer = components['authority'].issue(actor.tenant, actor.agent, 'trainer')
    evaluator = components['authority'].issue(actor.tenant, actor.agent, 'evaluator')
    populate(world, trainer, evaluator)
    rules = reflect(world.episodes(trainer))['rules']
    for rule in rules:
        world_guard.bind_rule(operator, task_id='combined', rule_id=rule['rule_id'],
            claim_ids=['claim-yes'], review_ref='synthetic-required-source-review')
    registry = Registry(world)
    model = registry.put(trainer, rules, compile_rules(rules), WorldPolicy(enabled=True))
    registry.freeze(evaluator, model)

    claim('claim-no', False)
    conflict = ledger.detect(actor, 'combined')[0]
    third, assessment, blocked = step('verified-heading', 'after-conflict')
    world_freeze_blocked = False
    try:
        registry.freeze(evaluator, model)
    except PermissionError:
        world_freeze_blocked = True
    world_result = world_guard.rulebook(actor, model)['uncertainty']

    start(components, task='independent', subject='synthetic-independent')
    claim('independent-source', True, task='independent')
    _, _, independent = step('verified-heading', 'unaffected', task='independent',
        dependencies=('independent-source',))
    final = OutputGuard(ledger, policy).render(actor, 'combined',
        [{'claim_id': 'claim-yes', 'decision_id': third.decision_id}], [assessment])

    adaptation_checkpoint = adaptation.checkpoint(actor, 'combined')
    propagation.checkpoint(actor, 'combined', 'combined-checkpoint')
    before_reset = adaptation.inspect(actor, 'combined')
    original_revision = ledger.revision(actor, 'combined')
    restarted = build(path, now=clock)
    resumed_actor, resumed_operator = restarted['actor'], restarted['operator']
    resumed_adaptation = restarted['adaptation']
    for principal in (resumed_actor, resumed_operator):
        resumed_adaptation.grant(resumed_operator, 'combined', principal,
            subject_scope='synthetic-subject', review_reference='synthetic-restart-reauthentication')
    resumed_adaptation.resume(resumed_actor, 'combined', adaptation_checkpoint)
    resumed_ledger = Ledger(restarted['engine'], clock=clock)
    resumed_envelope = Propagator(resumed_ledger).resume(resumed_actor, 'combined', 'combined-checkpoint')
    resumed_adaptation.reset(resumed_operator, 'combined', reason='synthetic-reset')
    after_reset = resumed_adaptation.inspect(resumed_actor, 'combined')
    preserved = (resumed_ledger.revision(resumed_actor, 'combined') == original_revision and
                 conflict.conflict_id in resumed_envelope['open_conflict_ids'] and
                 all(after_reset[k] == before_reset[k] for k in ('action_receipts', 'steps', 'constraints')))
    result = {'evidence_type': 'synthetic deterministic local integration; no provider inference',
        'state': str(path), 'task_id': 'combined', 'conflict_id': conflict.conflict_id,
        'initial': initial, 'correction_id': correction_id, 'corrected': corrected,
        'after_conflict': blocked, 'independent_work': independent,
        'world_model': {'model_id': model, 'freeze_blocked_after_conflict': world_freeze_blocked,
            'uncertainty': world_result, 'simulation_only': True},
        'restart': {'envelope': resumed_envelope, 'handler_effects': len(restarted['effects'])},
        'reset_preserved_current_conflicts_and_receipts': preserved,
        'output': final, 'paid_cost_usd': 0, 'provider_calls': 0,
        'production_activation': False, 'learned_model_gain_demonstrated': False}
    result['passed'] = (initial['semantic_status'] != 'verified' and
        corrected['semantic_status'] == 'verified' and blocked['semantic_status'] != 'verified' and
        blocked['handler_effects'] == 0 and independent['semantic_status'] == 'verified' and
        world_freeze_blocked and preserved and not restarted['effects'])
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True, help='Fresh explicitly selected local SQLite file')
    args = parser.parse_args(argv)
    try:
        result = run(args.state)
    except (ValueError, PermissionError, LookupError, RuntimeError) as error:
        print(json.dumps({'status': 'blocked', 'error_type': type(error).__name__, 'reason': str(error)}))
        return 2
    print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
