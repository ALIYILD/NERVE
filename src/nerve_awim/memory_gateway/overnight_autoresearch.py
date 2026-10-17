"""CPU-only registered selection machinery. No inference or promotion dispatch.

Replay must be supplied by the caller's fixed evaluator. This module never
converts historical or fixture results into fresh experimental evidence.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3

from . import scientific_candidates as candidates
from .experience_store_v2 import ExperienceStoreV2
from .scientific_format_episode_import import SCOPE

VERSION = 'overnight-autoresearch-20261017-v1'
RULE = dict(items=100, minimum_net_wins=6, maximum_losses=1,
            maximum_safety_errors=0, controls=['always-abstain', 'random'],
            wall_seconds=240, concurrency=4, identical_transport_resends=2,
            maximum_experiments_per_family=12, stop_consecutive_reverts=3)
SEAMS = {'conflict_check': 'abstention-rule', 'format_contract': 'prompt-fragment',
         'evidence_coverage': 'retrieval-order', 'abstention_check': 'abstention-rule'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


def write_once(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (canonical(value) + '\n').encode()
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if path.read_bytes() != data:
            raise ValueError('immutable_record_changed')
        return
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def read_v2(path):
    """Validate an existing v2 journal read-only, including chain and scope.

    This is host audit access, not an actor-facing authority bypass API. No
    authority is issued, store initialized, episode modified or inferred.
    """
    path = Path(path).resolve()
    store = object.__new__(ExperienceStoreV2)
    store.scope = SCOPE
    before = sha256(path.read_bytes()).hexdigest()
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        episodes, head = store._validate(db)
    if before != sha256(path.read_bytes()).hexdigest():
        raise ValueError('source_store_changed')
    return dict(episodes=episodes, head=head, source_sha256=before)


def rejection_key(seam, cluster):
    # Stable failure identity: adding episodes must not revive a rejected seam.
    return digest([seam, cluster['stratum'], cluster['failure_class']])


def propose(snapshot, rejected=()):
    """Generate one registered typed seam per genuine recorded failure cluster."""
    blocked = set(rejected)
    result = []
    for cluster in candidates._clusters(snapshot['episodes']):
        failure = cluster['failure_class']
        mutation = ('format_contract' if failure == 'schema_shape_failure' else
                    'abstention_check' if failure == 'abstention_contract_failure' else
                    candidates._mutation(failure))
        seam = SEAMS[mutation]
        key = rejection_key(seam, cluster)
        if key in blocked:
            continue
        body = dict(version=VERSION, seam=seam, mutation=mutation,
                    cluster=cluster, candidate=candidates.SPACE[mutation],
                    candidate_sha256=candidates.validate_config(candidates.SPACE[mutation]),
                    hypothesis=candidates.EFFECTS[mutation][0],
                    source_store_sha256=snapshot['source_sha256'],
                    store_head=snapshot['head'], rejection_key=key,
                    new_model_calls=0, evaluated=False, promotion_authorized=False)
        result.append(dict(body, proposal_sha256=digest(body)))
    return result


def register(directory, *, experiment_id, family, proposal, item_ids,
             bank_sha256, evaluator_sha256, incumbent, protected_sha256):
    if family not in ('A', 'B') or len(item_ids) != 100 or len(set(item_ids)) != 100:
        raise ValueError('family_and_100_unique_dev_items_required')
    if any(not isinstance(v, str) or len(v) != 64 or
           any(c not in '0123456789abcdef' for c in v)
           for v in (bank_sha256, evaluator_sha256, *protected_sha256.values())):
        raise ValueError('full_source_hashes_required')
    if proposal['proposal_sha256'] != digest({k:v for k,v in proposal.items() if k != 'proposal_sha256'}):
        raise ValueError('proposal_hash_changed')
    body = dict(version=VERSION, experiment_id=experiment_id, family=family,
                proposal=proposal, item_ids=item_ids, bank_sha256=bank_sha256,
                evaluator_sha256=evaluator_sha256, incumbent=incumbent,
                protected_sha256=protected_sha256, rule=RULE, split='dev',
                no_holdout=True, promotion_authorized=False)
    registration = dict(body, registration_sha256=digest(body))
    write_once(Path(directory)/'registration.json', registration)
    return registration


def decide(rows):
    if len(rows) != RULE['items'] or len({r['task_id'] for r in rows}) != len(rows):
        raise ValueError('complete_unique_100_item_receipt_required')
    fields = ('candidate', 'incumbent', 'always-abstain', 'random', 'safety_error')
    if any(type(row.get(k)) is not bool for row in rows for k in fields):
        raise ValueError('replayed_boolean_judgments_required')
    wins = sum(r['candidate'] and not r['incumbent'] for r in rows)
    losses = sum(r['incumbent'] and not r['candidate'] for r in rows)
    safety = sum(r['safety_error'] for r in rows)
    controls = {k: sum(r['candidate'] for r in rows) > sum(r[k] for r in rows)
                for k in RULE['controls']}
    keep = wins-losses >= 6 and losses <= 1 and safety == 0 and all(controls.values())
    return dict(wins=wins, losses=losses, ties=len(rows)-wins-losses,
                safety_errors=safety, controls=controls, kept=keep,
                verdict='kept' if keep else 'reverted')


def record(directory, replay, *, calls, cost_usd, elapsed_seconds):
    """Replay evaluator receives only the immutable study directory; no retry."""
    root = Path(directory)
    registration = json.loads((root/'registration.json').read_text())
    body = {k:v for k,v in registration.items() if k != 'registration_sha256'}
    if digest(body) != registration['registration_sha256'] or registration['rule'] != RULE:
        raise ValueError('registration_changed')
    rows = replay(root)  # Domain evaluator must deny network during this callback.
    if [r['task_id'] for r in rows] != registration['item_ids']:
        raise ValueError('registered_schedule_changed')
    if type(calls) is not int or not 0 <= calls <= 1200:
        raise ValueError('bounded_call_count_required')
    if not 0 <= cost_usd <= 12 or not 0 <= elapsed_seconds <= RULE['wall_seconds']:
        raise ValueError('experiment_budget_exceeded')
    result = dict(experiment_id=registration['experiment_id'], family=registration['family'],
                  registration_sha256=registration['registration_sha256'],
                  seam=registration['proposal']['seam'],
                  cluster=registration['proposal']['cluster']['cluster_sha256'],
                  hypothesis=registration['proposal']['hypothesis'],
                  receipt_sha256=digest(rows), calls=calls, cost_usd=cost_usd,
                  elapsed_seconds=elapsed_seconds, **decide(rows))
    # Persist rejection first; a crash can never erase a reverted seam.
    if not result['kept']:
        write_once(root/'rejection.json', dict(
            rejection_key=registration['proposal']['rejection_key'],
            receipt_sha256=result['receipt_sha256'], verdict='reverted'))
    write_once(root/'result.json', result)
    return result
