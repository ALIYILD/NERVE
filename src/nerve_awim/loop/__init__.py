"""Auditable local development loops. Human promotion remains external."""
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from ..memory_gateway.drift_monitor import DriftMonitor
from ..memory_gateway.site_router import SiteRouter
from .domains import Domain, get_domain


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',', ':'),allow_nan=False)


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


class Loop:
    def __init__(self, domain, directory='receipts/loop-local', *, episode_sink=None):
        self.domain=get_domain(domain)
        self.directory=Path(directory)
        self.directory.mkdir(parents=True,exist_ok=True)
        if episode_sink is not None:
            raise ValueError('external episode sinks cannot participate in atomic ingestion')
        from .experience import StudyMemory
        self.memory=StudyMemory(self.directory,self.domain.name)
        self.db=sqlite3.connect(self.directory/'loop.sqlite')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS registrations(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS receipts(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS rejected(seam TEXT,cluster TEXT,PRIMARY KEY(seam,cluster));
            CREATE TABLE IF NOT EXISTS stream(id INTEGER PRIMARY KEY,payload TEXT NOT NULL);
        ''')
        if self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='episodes'").fetchone():
            self.db.close()
            raise ValueError('legacy dual-store SDK directory requires explicit migration or a fresh directory')
        binding={'domain':self.domain.name,'skills':self.domain.skills,'reward_source':self.domain.reward_source,'version':self.domain.version}
        old=self.db.execute("SELECT payload FROM metadata WHERE key='domain'").fetchone()
        if old and old[0] != canonical(binding):
            raise ValueError('domain binding changed')
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO metadata VALUES('domain',?)",(canonical(binding),))

    def close(self):
        self.db.close()

    def _register(self, registration):
        identifier=digest(registration)
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO registrations VALUES(?,?)',(identifier,canonical(registration)))
        return identifier

    def learn(self, episodes):
        episodes=list(episodes)
        if not episodes or len(episodes)>10000:
            raise ValueError('one to 10000 recorded episodes required')
        for e in episodes:
            if set(e) not in ({'id','cluster','correct','source_receipt_sha256'}, {'id','cluster','correct','source_receipt_sha256','source_ordinal'}) or type(e['correct']) is not bool or not isinstance(e['id'],str) or not isinstance(e['cluster'],str):
                raise ValueError('typed recorded outcome required')
            h=e['source_receipt_sha256']
            if not isinstance(h,str) or len(h)!=64 or any(c not in '0123456789abcdef' for c in h):
                raise ValueError('source receipt SHA256 required')
        memory=self.memory.append(episodes)
        return {'learned':memory['count'], 'model_calls':0,
                'study_memory_count':memory['count'], 'provenance':'host-supplied receipt references; not signatures'}

    def propose(self):
        failures={}
        for e in self.memory.store.query(self.memory.actor)['episodes']:
            if e['evaluator_verdict']=='strict_incorrect':
                cluster=e['failure_class']
                failures[cluster]=failures.get(cluster,0)+1
        for cluster,count in sorted(failures.items(),key=lambda kv:(-kv[1],kv[0])):
            seam='prompt-fragment'
            if self.db.execute('SELECT 1 FROM rejected WHERE seam=? AND cluster=?',(seam,cluster)).fetchone():
                continue
            candidate={'skill':'candidate:context','seam':seam,'cluster':cluster,'failures':count,
                       'domain':self.domain.name,'hypothesis':'use observable structured context when summaries are unavailable',
                       'evidence_hash':digest(self.memory.episodes())}
            candidate['registration_hash']=self._register(candidate)
            return candidate
        return None

    def evaluate(self, candidate, bank, gate='dev'):
        if gate != 'dev':
            raise PermissionError('sealed evaluation requires external signed gate; SDK never opens holdouts')
        bank=list(bank)
        if not bank or len(bank)>12000 or len({r['id'] for r in bank}) != len(bank):
            raise ValueError('unique bounded dev items required')
        identifier=candidate.get('registration_hash')
        registered=self.db.execute('SELECT payload FROM registrations WHERE id=?',(identifier,)).fetchone()
        payload={k:v for k,v in candidate.items() if k!='registration_hash'}
        if not registered or registered[0]!=canonical(payload):
            raise ValueError('exact registered candidate required')
        registration={'candidate_hash':identifier,'bank_hash':digest(bank),'gate':'dev',
                      'keep_rule':{'net_wins':6,'max_losses':1,'safety_errors':0,'beat_controls':True},
                      'controls':['always-abstain','random'],'model_calls':0,
                      'domain_version':self.domain.version,
                      'evaluator_source_sha256':{name:sha256((Path(__file__).parent/name).read_bytes()).hexdigest()
                                                 for name in ('__init__.py','domains.py')}}
        study=self._register(registration)  # Persist before evaluator execution.
        prior=self.db.execute('SELECT payload FROM receipts WHERE id=?',(study,)).fetchone()
        if prior:
            return json.loads(prior[0])
        rows=[]
        for item in bank:
            scores={s:self.domain.correct(self.domain.predict(s,self.domain.public_input(item)),item) for s in
                    [self.domain.skills[0],candidate['skill'],'always-abstain','random']}
            rows.append({'item':item,'scores':scores})
        incumbent=self.domain.skills[0]; skill=candidate['skill']
        wins=sum(r['scores'][skill] and not r['scores'][incumbent] for r in rows)
        losses=sum(r['scores'][incumbent] and not r['scores'][skill] for r in rows)
        safety=sum(r['item']['safety'] and not r['scores'][skill] for r in rows)
        totals={s:sum(r['scores'][s] for r in rows) for s in rows[0]['scores']}
        controls=all(totals[skill]>totals[s] for s in ('always-abstain','random'))
        kept=wins-losses>=6 and losses<=1 and safety==0 and controls
        receipt={'study':study,'registration':registration,'rows':rows,'wins':wins,'losses':losses,
                 'ties':len(rows)-wins-losses,'safety_errors':safety,'totals':totals,
                 'controls_passed':controls,'kept':kept,'verdict':'kept' if kept else 'reverted',
                 'model_calls':0,'synthetic':True,'promotion':False}
        with self.db:
            self.db.execute('INSERT INTO receipts VALUES(?,?)',(study,canonical(receipt)))
            if not kept:
                self.db.execute('INSERT OR IGNORE INTO rejected VALUES(?,?)',(candidate['seam'],candidate['cluster']))
        return receipt

    def adapt(self, stream, *, stop_after=None):
        rows=list(stream)
        if not rows or len(rows)>12000 or len({r['id'] for r in rows})!=len(rows):
            raise ValueError('unique bounded recorded stream required')
        registration={'domain':self.domain.name,'stream_hash':digest(rows),'retained':self.domain.skills,
                      'warmup':30,'threshold':8.,'allowance':.05,'window':20,'verification_window':10,
                      'margin':.2,'rollback_quarantine':60,'monitor_reference':'first-retained-skill','expected_detection_delay':60,'model_calls':0,'synthetic':True}
        study=self._register(registration)
        with self.db:
            old=self.db.execute("SELECT payload FROM metadata WHERE key='adapt_binding'").fetchone()
            if old and old[0]!=study:
                raise ValueError('stream or registered configuration changed on resume')
            self.db.execute("INSERT OR IGNORE INTO metadata VALUES('adapt_binding',?)",(study,))
        limit=len(rows) if stop_after is None else stop_after
        if type(limit) is not int or not 0 <= limit <= len(rows):
            raise ValueError('invalid stop boundary')
        for index in range(limit):
            with self.db:
                # One transaction binds state advancement to receipt persistence.
                if self.db.execute('SELECT 1 FROM stream WHERE id=?',(index,)).fetchone():
                    continue
                state=self.db.execute("SELECT payload FROM metadata WHERE key='adapt_state'").fetchone()
                if state:
                    state=json.loads(state[0]); monitor=DriftMonitor(**state['monitor']); router=SiteRouter(**state['router'])
                else:
                    monitor=DriftMonitor(); router=SiteRouter(list(self.domain.skills),self.domain.skills[0])
                row=rows[index]
                rewards=row['rewards']; before=router.current
                observed=False if row.get('degraded',False) else rewards[before]
                detected=monitor.update(correct=rewards[self.domain.skills[0]],discordance=len(set(rewards.values()))>1,abstention=row['abstention'])
                events=router.update(rewards,observed,detected)
                receipt={'index':index,'input_hash':digest(row),'before':before,'after':router.current,
                         'correct':observed,'drift':detected,'events':events,'model_calls':0,'study':study}
                self.db.execute('INSERT INTO stream VALUES(?,?)',(index,canonical(receipt)))
                self.db.execute("INSERT OR REPLACE INTO metadata VALUES('adapt_state',?)",(canonical({'monitor':asdict(monitor),'router':asdict(router)}),))
        return {'study':study,'registration':registration,'receipts':[json.loads(r[0]) for r in self.db.execute('SELECT payload FROM stream ORDER BY id')], 'model_calls':0}

    def status(self):
        return {'domain':self.domain.name,'incumbents':list(self.domain.skills),'signing_queue':[],
                'model_calls':0,'real_world_reward':False,'automatic_promotion':False,
                'studies':self.db.execute('SELECT COUNT(*) FROM receipts').fetchone()[0],
                'adapt_items':self.db.execute('SELECT COUNT(*) FROM stream').fetchone()[0],
                'boundaries':['synthetic ground truth','host-declared sandbox retained skills',
                              'scientific demo is not canonical scientific evaluation',
                              'study-v2 companion preserves original format-probe v2 schema']}
