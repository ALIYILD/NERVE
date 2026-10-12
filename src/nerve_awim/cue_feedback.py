"""Bounded observational cue feedback for discovery, never deployment authority.

Evaluator counts do not prove that a cue was applied, that it caused an outcome,
that samples are independent, or that a historical approval remains valid. Text
is untrusted proposal context; identifiers of tasks, episodes, patients, candidate
records and held-out reports are intentionally absent. ``cue_digest`` hashes only
the exact UTF-8 cue text; it is not Cue.content_hash or an evaluation-report digest.
This context supports instruction cues only; prefix history must not be converted.
"""
from hashlib import sha256
import json
import re

from .cue_engine import Cue, safety_reason

MAX_CONTEXT_BYTES = 8192
SOURCE = 'trusted_evaluator_feedback'
_TOP_KEYS = {'schema_version', 'profile_key', 'task_type', 'source', 'causal_evidence',
             'authorization_granted', 'candidates'}
_CANDIDATE_KEYS = {'cue_text', 'cue_digest', 'status', 'observations', 'correct', 'safe'}
_DIGEST = re.compile(r'[a-f0-9]{64}\Z')


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def cue_text_digest(text):
    return sha256(text.encode('utf-8')).hexdigest()


def validate_learning_context(value, profile_key, task_type):
    """Validate exact binding and return a deeply independent normalized snapshot."""
    if (type(profile_key) is not str or not _DIGEST.fullmatch(profile_key)
            or type(task_type) is not str or not task_type.strip()):
        raise ValueError('exact profile hash and task type required')
    if type(value) is not dict or set(value) != _TOP_KEYS:
        raise ValueError('strict learning context schema required')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['profile_key'] != profile_key or value['task_type'] != task_type
            or value['source'] != SOURCE or value['causal_evidence'] is not False
            or value['authorization_granted'] is not False):
        raise ValueError('unprivileged observational context with exact binding required')
    candidates = value['candidates']
    if type(candidates) is not list or len(candidates) > 8:
        raise ValueError('at most eight feedback cue entries required')
    normalized, seen = [], set()
    for entry in candidates:
        if type(entry) is not dict or set(entry) != _CANDIDATE_KEYS:
            raise ValueError('strict feedback entry schema required')
        cue = Cue('feedback-validation', 1, entry['cue_text'], 'instruction', profile_key,
                  (task_type,), SOURCE)
        if safety_reason(cue):
            raise ValueError('unsafe cue text cannot enter discovery feedback')
        digest = cue_text_digest(cue.text)
        if type(entry['cue_digest']) is not str or entry['cue_digest'] != digest or digest in seen:
            raise ValueError('unique exact cue text digest required')
        seen.add(digest)
        if type(entry['status']) is not str or entry['status'] not in ('approved', 'revoked'):
            raise ValueError('observed historical approved or revoked candidate required')
        n = entry['observations']
        if type(n) is not int or not 1 <= n <= 64:
            raise ValueError('bounded positive observation count required')
        if any(type(entry[key]) is not int or not 0 <= entry[key] <= n for key in ('correct', 'safe')):
            raise ValueError('integer correct and safe counts must fit observations')
        normalized.append({'cue_text': cue.text, 'cue_digest': digest, 'status': entry['status'],
                           'observations': n, 'correct': entry['correct'], 'safe': entry['safe']})
    snapshot = {'schema_version': 1, 'profile_key': profile_key, 'task_type': task_type,
                'source': SOURCE, 'causal_evidence': False, 'authorization_granted': False,
                'candidates': normalized}
    # Cue construction validates task binding when populated; check empty contexts too.
    Cue('feedback-binding', 1, 'Check.', 'instruction', profile_key, (task_type,), SOURCE)
    try:
        encoded = _canonical(snapshot).encode('utf-8')
    except (TypeError, ValueError, UnicodeError):
        raise ValueError('valid bounded UTF-8 context required') from None
    if len(encoded) > MAX_CONTEXT_BYTES:
        raise ValueError('learning context exceeds byte cap')
    return snapshot


def learning_context_digest(value):
    """Stable canonical digest of a validated snapshot, without claiming causality."""
    if type(value) is not dict:
        raise ValueError('learning context object required')
    snapshot = validate_learning_context(value, value.get('profile_key'), value.get('task_type'))
    return sha256(_canonical(snapshot).encode('utf-8')).hexdigest()
