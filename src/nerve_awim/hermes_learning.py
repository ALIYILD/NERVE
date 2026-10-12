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
