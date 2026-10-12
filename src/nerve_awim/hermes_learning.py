"""NERVE-governed evidence -> Hermes lesson proposal -> independent evaluation."""
from .skill_proposals import generate_skill_proposal
from .skill_validation import evaluate_lesson
from .learning_study import validate_stream


def propose_and_evaluate(ledger, actor, *, runtime, context, evidence_episodes,
                         evaluator_revision, study, predict, judge, uncertainty=None):
    """Host supplies approved research evidence, task data and independent judge.

    Raw web research is not performed here. Runtime gets no expected answers.
    A failed evaluation leaves a pending proposal, never an approved memory.
    """
    ledger.authority.require(actor, 'read')
    ledger.authority.require(actor, 'propose')
    from .uncertainty.adapters import memory_boundary
    memory_boundary(ledger, actor, context, uncertainty)
    study = validate_stream(study)
    def generate(request):
        envelope = uncertainty.handoff(actor) if uncertainty is not None else None
        if envelope is not None:
            request = {**request, 'uncertainty': envelope}
        research = runtime.execute('research', {**request, 'output_schema':
            'Return exactly summary (string) and episodes (unchanged ordered IDs).'},
            tenant=actor.tenant_id, agent=actor.agent_id)
        expected = [e['episode_id'] for e in request['evidence']]
        if type(research) is not dict or set(research) != {'summary', 'episodes'} \
                or research['episodes'] != expected or type(research['summary']) is not str \
                or not 1 <= len(research['summary']) <= 2048:
            raise ValueError('bounded source-linked research summary required')
        if uncertainty is not None:
            request = {**request, 'uncertainty': uncertainty.handoff(actor, envelope)}
        built = runtime.execute('skill_builder', {**request, 'research_summary':research['summary'],
            'output_schema':'Return exactly lesson (string) and episodes (unchanged ordered IDs).'},
            tenant=actor.tenant_id, agent=actor.agent_id)
        if uncertainty is not None:
            uncertainty.handoff(actor, request['uncertainty'])
            uncertainty.permit_learning(actor)
        return built
    proposal = generate_skill_proposal(ledger, actor, context=context,
        episodes=evidence_episodes, evaluator_revision=evaluator_revision,
        generator=generate)
    record = ledger.status(actor, proposal)
    evaluation = evaluate_lesson(record.content, study, predict=predict, judge=judge)
    result = {'proposal_id':proposal, 'memory_status':ledger.status(actor, proposal).status,
            'evaluation':evaluation, 'promotion_authorized':False,
            'runtime_contract':'Hermes text-only v1; host owns provider isolation'}

    if uncertainty is not None:
        uncertainty.permit_learning(actor)
        result['uncertainty'] = uncertainty.handoff(actor)
        result['uncertainty_result'] = uncertainty.final([{'claim_id': c.claim_id} for c in uncertainty.ledger.claims(uncertainty.actor, uncertainty.task_id)])
    return result


def propose_world_rules(ledger, actor, *, runtime, offline_fixture=False):
    """Opt-in structured offline bridge; never gives Hermes final answers or roles.

    Live use fails closed until durable provider-cost reservation is integrated.
    Existing text lesson API and its behavior remain unchanged.
    """
    if offline_fixture is not True:
        raise PermissionError('live world-model proposals require a budgeted provider adapter')
    from .world_model.contracts import exact, Rule
    from .uncertainty.world_model_adapter import checkpoint_state
    with ledger.db() as con:
        uncertainty_state = checkpoint_state(ledger, actor, {}, con=con)
    episodes = ledger.episodes(actor, 'train')
    evidence = {row['id']: row for episode in episodes for row in episode['transitions']}
    request = {'evidence': episodes, 'output_schema': 'Exactly rules: list of world-model Rule v1 records.',
               'authority': 'untrusted proposals only; no evaluation or deployment access'}
    if uncertainty_state is not None:
        request['uncertainty'] = uncertainty_state
    result = runtime.execute('skill_builder', request, tenant=actor.tenant, agent=actor.agent)
    exact(result, ('rules',))
    if type(result['rules']) is not list or not 1 <= len(result['rules']) <= 256:
        raise ValueError('bounded structured rules required')
    rules = [Rule.load(raw).to_dict() for raw in result['rules']]
    for rule in rules:
        for reference in rule['supporting_transition_ids'] + rule['contradicting_transition_ids']:
            if reference not in evidence:
                raise ValueError('invented or nontraining evidence reference')
    response = {'rules': rules, 'evidence_mode': 'offline runtime fixture',
                'eligibility': False, 'deployment_authorized': False}
    if uncertainty_state is not None:
        # Rebuild after the call: omitting conflict IDs in provider JSON cannot
        # discard them, and newly arrived evidence supersedes the sent envelope.
        with ledger.db() as con:
            response['uncertainty'] = checkpoint_state(ledger, actor, {'proposal':{'rules':rules}}, con=con)
    return response
