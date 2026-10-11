"""Build pending procedural-memory proposals from verified outcome references."""
import sqlite3
import time
from .memory_v18 import _id


def propose_skill(ledger, actor, *, context, lesson, episodes, evaluator_revision):
    """Trusted-host helper, not an autonomous reflector or approval mechanism.

    The supplied lesson remains unverified text until independently reviewed.
    Evidence links support provenance, not proof that the proposed lesson works.
    """
    ledger.authority.require(actor, 'propose')
    _id(context, 'context')
    _id(evaluator_revision, 'evaluator revision')
    episodes = tuple(episodes)
    if not 3 <= len(episodes) <= 20 or len(set(episodes)) != len(episodes):
        raise ValueError('3 to 20 distinct successful evidence episodes required')
    for episode in episodes:
        _id(episode, 'episode')
    with sqlite3.connect(ledger.path) as con:
        con.execute('''CREATE TABLE IF NOT EXISTS skill_evidence (
            proposal TEXT, episode TEXT, revision TEXT,
            PRIMARY KEY(proposal,episode))''')
        for episode in episodes:
            row = con.execute('''SELECT m.context,m.status FROM memory_utility u
                JOIN trusted_memory_v18 m ON m.memory_id=u.memory
                WHERE u.tenant=? AND u.agent=? AND u.episode=? AND u.revision=?
                AND u.status='judged' AND u.success=1
                AND (m.valid_until IS NULL OR m.valid_until>?)''',
                (actor.tenant_id, actor.agent_id, episode, evaluator_revision, int(time.time()))).fetchone()
            if row != (context, 'approved'):
                raise ValueError('successful current in-scope evidence required')
    # Proposal is intentionally never approved here. Host reviewer rechecks
    # evidence freshness and independently validates the lesson before approval.
    mid = ledger.propose(actor, context=context, content=lesson, kind='procedural',
                         source_id='verified-episode-proposal')
    with sqlite3.connect(ledger.path) as con:
        con.executemany('INSERT INTO skill_evidence VALUES(?,?,?)',
                        [(mid, episode, evaluator_revision) for episode in episodes])
    return mid
