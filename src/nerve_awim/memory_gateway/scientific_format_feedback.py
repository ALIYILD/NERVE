"""Import completed probe outcomes and register bounded, unevaluated hypotheses."""
from hashlib import sha256
from pathlib import Path
import re
import stat

from . import scientific_format_episode_import as importer
from . import scientific_candidates as candidates
from .scientific_episode_import import canonical, digest, _save_exact
from .research_supervisor import _exclusive

VERSION = 'scientific-format-feedback-v1'
RULES = {
    'schema_shape_failure': ('format_contract', False),
    'abstention_contract_failure': ('abstention_check', True),
}
_RULES = canonical(RULES)


def sources():
    pins = importer.sources()
    pins.update(candidates.sources())
    for name in ('src/nerve_awim/memory_gateway/scientific_format_feedback.py',
                 'scripts/run_scientific_format_feedback.py'):
        pins[name] = sha256((importer.pilot.ROOT / name).read_bytes()).hexdigest()
    return pins


def propose(store, actor, expected_digest):
    """Registered templates only; no code generation, evaluation or promotion."""
    if canonical(RULES) != _RULES:
        raise ValueError('frozen_failure_rules_changed')
    if type(expected_digest) is not str or not re.fullmatch('[0-9a-f]{64}', expected_digest):
        raise ValueError('full_model_digest_required')
    result = store.query(actor)
    report = dict(status=result['status'], proposals=[], model_calls=0,
                  model_research_agent=False, holdout_accessed=False,
                  promotion_authorized=False, negative_evidence_enforced=False)
    if result['status'] != 'live':
        return report
    report['store_head'] = result['head']
    for failure, (mutation, constrained) in sorted(RULES.items()):
        rows = [r for r in result['episodes'] if r['failure_class'] == failure]
        if not rows:
            continue
        clusters = candidates._clusters(rows)
        config = dict(candidates.SPACE[mutation])
        base_hash = candidates.validate_config(config)
        policy = dict(base_candidate_config=config, constrained=constrained,
                      model_digest=expected_digest)
        body = dict(version=VERSION, candidate=config, candidate_sha256=base_hash,
                    execution_policy=policy, execution_policy_sha256=digest(policy),
                    mutation=mutation, failure_class=failure, clusters=clusters,
                    store_head=result['head'], source_sha256=sources(),
                    predicted_effect=('Test whether contract-first instructions reduce schema copying.'
                                      if failure == 'schema_shape_failure' else
                                      'Test whether an explicit evidence check reduces inconsistent abstention.'),
                    risk='May increase abstention or retain the same formatting failures; untested.',
                    evaluated=False, promotion_authorized=False,
                    next_step='requires_fresh_registered_development_evaluation')
        report['proposals'].append(dict(body, hypothesis_sha256=digest(body)))
    return report


def validate_proposal(proposal, store, actor, expected_digest):
    # Exact reconstruction binds rule, every cluster member, policy and current scope.
    expected = propose(store, actor, expected_digest)
    if canonical(proposal) not in [canonical(p) for p in expected['proposals']]:
        raise ValueError('authoritative_feedback_proposal_changed')
    return True


def run(directory, episode_directory, study_directory, study_journal, expected_digest,
        *, disabled=False):
    if type(disabled) is not bool:
        raise ValueError('boolean_disabled_required')
    if disabled:
        return dict(status='off', new_model_calls=0)
    root, episodes, study, journal = [Path(p).resolve() for p in
                                    (directory, episode_directory, study_directory, study_journal)]
    dirs = (root, episodes, study)
    if len(set((root, episodes, study, journal))) != 4 or any(
            a in b.parents for a in dirs for b in dirs if a != b) or any(d in journal.parents for d in dirs):
        raise ValueError('separate_feedback_paths_required')
    pins = sources()
    imported = importer.run(episodes, study, journal, expected_digest)
    gateway, _, _, _, reader = importer.pilot._state(episodes / 'authority.sqlite')
    store = importer.ExperienceStoreV2(episodes / 'experiences.sqlite', gateway, importer.SCOPE)
    generated = propose(store, reader, expected_digest)
    for proposal in generated['proposals']:
        validate_proposal(proposal, store, reader, expected_digest)
    report = dict(version=VERSION, status='registered' if generated['proposals'] else 'no_proposals',
                  paths=[str(p) for p in (root, episodes, study, journal)],
                  source_sha256=pins, import_receipt_sha256=digest(imported),
                  generation=generated, new_model_calls=0, evaluated=False,
                  promotion_authorized=False, model_weights_trained=False,
                  goal_achieved=False)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if stat.S_IMODE(root.stat().st_mode) != 0o700:
        raise ValueError('private_feedback_directory_required')
    with _exclusive(root):
        if (canonical(importer.run(episodes, study, journal, expected_digest)) != canonical(imported)
                or canonical(propose(store, reader, expected_digest)) != canonical(generated)
                or sources() != pins):
            raise ValueError('feedback_inputs_changed')
        _save_exact(root / 'report.json', report)
    return report
