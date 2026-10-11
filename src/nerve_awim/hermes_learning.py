"""NERVE-governed evidence -> Hermes lesson proposal -> independent evaluation."""
from .skill_proposals import generate_skill_proposal
from .skill_validation import evaluate_lesson
from .learning_study import validate_stream


def propose_and_evaluate(ledger, actor, *, runtime, context, evidence_episodes,
                         evaluator_revision, study, predict, judge):
    """Host supplies approved research evidence, task data and independent judge.

    Raw web research is not performed here. Runtime gets no expected answers.
    A failed evaluation leaves a pending proposal, never an approved memory.
    """
    ledger.authority.require(actor, 'read')
    ledger.authority.require(actor, 'propose')
    study = validate_stream(study)
    def generate(request):
        research = runtime.execute('research', {**request, 'output_schema':
            'Return exactly summary (string) and episodes (unchanged ordered IDs).'},
            tenant=actor.tenant_id, agent=actor.agent_id)
        expected = [e['episode_id'] for e in request['evidence']]
        if type(research) is not dict or set(research) != {'summary', 'episodes'} \
                or research['episodes'] != expected or type(research['summary']) is not str \
                or not 1 <= len(research['summary']) <= 2048:
            raise ValueError('bounded source-linked research summary required')
        return runtime.execute('skill_builder', {**request, 'research_summary':research['summary'],
            'output_schema':'Return exactly lesson (string) and episodes (unchanged ordered IDs).'},
            tenant=actor.tenant_id, agent=actor.agent_id)
    proposal = generate_skill_proposal(ledger, actor, context=context,
        episodes=evidence_episodes, evaluator_revision=evaluator_revision,
        generator=generate)
    record = ledger.status(actor, proposal)
    evaluation = evaluate_lesson(record.content, study, predict=predict, judge=judge)
    return {'proposal_id':proposal, 'memory_status':ledger.status(actor, proposal).status,
            'evaluation':evaluation, 'promotion_authorized':False,
            'runtime_contract':'Hermes text-only v1; host owns provider isolation'}
