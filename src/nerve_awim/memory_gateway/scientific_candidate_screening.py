"""Screen registered research proposals against host-adjudicated negative memory.

No inference, holdout read, efficacy verdict, promotion or rejection is created by
this runner. Initializing an empty journal is explicit and never restores lost data.
"""
from hashlib import sha256
import json
from pathlib import Path
import stat

from . import scientific_candidate_registration as registration
from .scientific_negative_evidence import NegativeEvidenceJournal
from .research_supervisor import _exclusive

VERSION = 'scientific-candidate-screening-v1'


def sources():
    pins = registration.sources()
    for name in ('src/nerve_awim/memory_gateway/scientific_negative_evidence.py',
                 'src/nerve_awim/memory_gateway/scientific_candidate_screening.py',
                 'scripts/screen_scientific_candidates.py'):
        pins[name] = sha256((registration.importer.pilot.ROOT/name).read_bytes()).hexdigest()
    return pins


def _private_directory(path, *, create=False):
    if create:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not path.is_dir() or stat.S_IMODE(path.stat().st_mode) != 0o700:
        raise ValueError('private_directory_required')


def run(directory, registration_directory, history_directory, *, initialize_history=False):
    if type(initialize_history) is not bool:
        raise ValueError('explicit_boolean_initialization_required')
    root, registered, history = [Path(p).resolve() for p in (directory,registration_directory,history_directory)]
    if len({root,registered,history}) != 3 or any(a in b.parents for a in (root,registered,history) for b in (root,registered,history) if a!=b):
        raise ValueError('separate_research_directories_required')
    _private_directory(registered)
    report_path = registered/'report.json'
    mode = report_path.lstat()
    if not stat.S_ISREG(mode.st_mode) or stat.S_IMODE(mode.st_mode) != 0o600:
        raise ValueError('private_registered_report_required')
    with report_path.open('rb') as stream:
        raw = stream.read(1024*1024+1)
    if len(raw)>1024*1024:
        raise ValueError('bounded_registered_report_required')
    original = json.loads(raw)
    episodes = Path(original['episode_directory']).resolve()
    if any(p==episodes or p in episodes.parents or episodes in p.parents for p in (root,history)):
        raise ValueError('separate_episode_directory_required')
    pins = sources()
    proposals = original['generation']['proposals']
    checked = registration.run(registered,episodes,
        research_agent_enabled=original['generation']['mode']=='deterministic_failure_rules',
        max_proposals=max(1,len(proposals)))
    if registration.importer.canonical(original)!=registration.importer.canonical(checked):
        raise ValueError('registration_changed')
    gateway,_,_,reviewer,reader = registration.importer.pilot._state(episodes/'authority.sqlite')
    store = registration.importer.ExperienceStore(episodes/'experiences.sqlite',gateway,registration.importer.SCOPE)
    _private_directory(history,create=initialize_history)
    with _exclusive(history):
        journal = NegativeEvidenceJournal(history/'rejections.sqlite',gateway,registration.importer.SCOPE,store)
        if initialize_history and not journal.path.exists():
            if any(p.name!='supervisor.lock' for p in history.iterdir()):
                raise ValueError('existing_history_missing_degraded')
            registration.importer._save_exact(history/'identity.json',
                {'version':VERSION,'purpose':'negative-evidence-history','episode_directory':str(episodes)})
            journal.initialize(reviewer)
        expected_identity = {'version':VERSION,'purpose':'negative-evidence-history','episode_directory':str(episodes)}
        if journal.path.exists():
            identity = history/'identity.json'
            if not identity.is_file():
                raise ValueError('history_identity_missing')
            registration.importer._save_exact(identity,expected_identity)
        decision = journal.filter(reader,proposals)
        result = dict(version=VERSION,status=('screened' if decision['status']=='live' else 'blocked'),
            source_sha256=pins,registration_sha256=sha256(raw).hexdigest(),
            registration_directory=str(registered),history_directory=str(history),decision=decision,
            new_model_calls=0,holdout_accessed=False,evaluated=False,promotion_authorized=False,
            rejection_receipts_created=0)
        if sources()!=pins or report_path.read_bytes()!=raw or journal.filter(reader,proposals)!=decision:
            raise ValueError('screening_inputs_changed')
        _private_directory(root,create=True)
        with _exclusive(root):
            registration.importer._save_exact(root/'report.json',result)
    return result
