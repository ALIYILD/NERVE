"""NERVE Learn: local opt-in agent experience memory (experimental).

Does not retrain models, execute arbitrary instructions, or share data remotely.
Separate agent namespaces and explicit feedback prevent automatic promotion of
unverified outputs into trusted skills.
"""
from dataclasses import dataclass
from pathlib import Path
import json, sqlite3, time, uuid

@dataclass(frozen=True)
class Experience:
    experience_id: str
    agent_id: str
    task: str
    outcome: str
    score: float | None
    created_at: int

class LearningStore:
    def __init__(self, path):
        self.path=str(Path(path))
        with sqlite3.connect(self.path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS experiences
                (experience_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL,
                task TEXT NOT NULL, outcome TEXT NOT NULL,
                score REAL, created_at INTEGER NOT NULL)""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_agent ON experiences(agent_id)")
    def record(self, agent_id, task, outcome):
        if not all(isinstance(x,str) and 0<len(x)<=4000 for x in (agent_id,task,outcome)):
            raise ValueError("nonempty bounded strings required")
        eid=uuid.uuid4().hex
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO experiences VALUES (?,?,?,?,?,?)",
                       (eid,agent_id,task,outcome,None,int(time.time())))
        return eid
    def feedback(self, agent_id, experience_id, score):
        if not isinstance(score,(int,float)) or isinstance(score,bool) or not 0<=score<=1:
            raise ValueError("score must be between zero and one")
        with sqlite3.connect(self.path) as db:
            result=db.execute("UPDATE experiences SET score=? WHERE experience_id=? AND agent_id=?",
                              (float(score),experience_id,agent_id))
            if result.rowcount!=1:raise LookupError("experience not found for agent")
    def recall(self, agent_id, query, limit=5):
        if not isinstance(agent_id,str) or not agent_id or not isinstance(query,str):
            raise ValueError("invalid query")
        if not isinstance(limit,int) or not 1<=limit<=20:raise ValueError("invalid limit")
        # Literal substring match, not SQL wildcard injection.
        with sqlite3.connect(self.path) as db:
            rows=db.execute("""SELECT experience_id,agent_id,task,outcome,score,created_at
                FROM experiences WHERE agent_id=? AND instr(lower(task),lower(?))>0
                ORDER BY (score IS NULL), score DESC, created_at DESC LIMIT ?""",
                (agent_id,query,limit)).fetchall()
        return [Experience(*row) for row in rows]
    def suggest(self,agent_id,query,min_score=.8):
        return [x for x in self.recall(agent_id,query) if x.score is not None
                and x.score>=min_score]

    def rated_history(self, agent_id, context, limit=500):
        """Recent evaluated experiences for one exact agent/context.

        Unlike task substring search, exact context matching avoids pulling
        examples from adjacent capabilities. Returns oldest-to-newest order.
        This is a local convenience namespace, NOT authentication.
        """
        if not all(isinstance(x, str) and 0 < len(x) <= 256
                   for x in (agent_id, context)):
            raise ValueError("nonempty bounded agent and context required")
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("history limit must be 1..1000")
        with sqlite3.connect(self.path) as db:
            rows = db.execute(
                """SELECT experience_id,agent_id,task,outcome,score,created_at
                   FROM experiences
                   WHERE agent_id=? AND task=? AND score IS NOT NULL
                   ORDER BY rowid DESC LIMIT ?""",
                (agent_id, context, limit),
            ).fetchall()
        return [Experience(*row) for row in reversed(rows)]
