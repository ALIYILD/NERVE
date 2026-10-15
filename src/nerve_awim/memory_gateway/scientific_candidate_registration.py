"""Register bounded hypotheses from completed synthetic episodes; no evaluator dispatch."""
from hashlib import sha256
from pathlib import Path
import json
import stat

from . import scientific_episode_import as importer
from . import scientific_candidates as candidates
from .research_supervisor import _exclusive

VERSION = 'scientific-candidate-registration-v1'


def sources():
    result = importer.sources()
    for name in ('src/nerve_awim/memory_gateway/scientific_candidates.py',
                 'src/nerve_awim/memory_gateway/scientific_candidate_registration.py',
                 'scripts/register_scientific_candidates.py'):
        result[name] = sha256((importer.pilot.ROOT / name).read_bytes()).hexdigest()
    return result


def run(directory, episode_directory, *, research_agent_enabled=True, max_proposals=4):
    if type(research_agent_enabled) is not bool or type(max_proposals) is not int or not 1 <= max_proposals <= 4:
        raise ValueError('bounded_host_configuration_required')
    root, episodes = Path(directory).resolve(), Path(episode_directory).resolve()
    if root == episodes or root in episodes.parents or episodes in root.parents:
        raise ValueError('separate_registration_directory_required')
    pins = sources()
    if stat.S_IMODE(episodes.stat().st_mode) != 0o700:
        raise ValueError('private_episode_directory_required')
    # Require a completed import; never initialize a journal as a side effect.
    for name in ('report.json','experiences.sqlite','authority.sqlite','episodes.jsonl','episodes.jsonl.manifest.json'):
        path = episodes / name
        mode = path.lstat()
        allowed_modes = (0o600, 0o644) if name == 'authority.sqlite' else (0o600,)
        if not stat.S_ISREG(mode.st_mode) or stat.S_IMODE(mode.st_mode) not in allowed_modes:
            raise ValueError('complete_private_import_required')
    with (episodes / 'report.json').open('rb') as stream:
        raw = stream.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError('bounded_import_report_required')
    receipt = json.loads(raw)
    checked = importer.run(episodes, receipt['validation_directory'], receipt['validation_journal'], receipt['expected_digest'])
    if importer.canonical(receipt) != importer.canonical(checked):
        raise ValueError('import_receipt_changed')
    gateway, _, _, _, reader = importer.pilot._state(episodes / 'authority.sqlite')
    store = importer.ExperienceStore(episodes / 'experiences.sqlite', gateway, importer.SCOPE)
    before = store.status(reader)
    generated = candidates.propose(store, reader, research_agent_enabled=research_agent_enabled,
                                   max_proposals=max_proposals)
    for proposal in generated['proposals']:
        candidates.validate_hypothesis(proposal, store, reader)
    if store.status(reader) != before or sources() != pins:
        raise ValueError('generation_inputs_changed')
    result = dict(version=VERSION, status=('registered' if generated['proposals'] else 'no_proposals'), source_sha256=pins,
                  episode_directory=str(episodes), import_receipt_sha256=sha256(raw).hexdigest(),
                  store_status=before, generation=generated, new_model_calls=0,
                  holdout_opened=False, evaluated=False, promotion_authorized=False,
                  next_step='requires_registered_development_evaluation')
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if stat.S_IMODE(root.stat().st_mode) != 0o700:
        raise ValueError('private_registration_directory_required')
    with _exclusive(root):
        # Recheck completed source and authority before publishing proposals.
        if store.status(reader) != before or (episodes/'report.json').read_bytes() != raw or sources() != pins:
            raise ValueError('generation_inputs_changed')
        importer._save_exact(root/'report.json', result)
    return result
