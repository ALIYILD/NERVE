"""Synthetic non-patient contracts; no remote model or real reward implied."""
from dataclasses import dataclass
import random

@dataclass(frozen=True)
class Domain:
    name: str
    skills: tuple[str,str]
    reward_source: str = 'synthetic ground truth'

    version: str = 'synthetic-contract-v2'

    def bank(self, size=100, *, seed=20261017):
        if type(size) is not int or not 1 <= size <= 12000:
            raise ValueError('bounded item budget required')
        rng=random.Random(seed)
        rows=[]
        for i in range(size):
            missing=i%3==0
            if self.name == 'scientific':
                # Extract the sign of a reported synthetic measurement.
                value=rng.choice((-1,1))*rng.randint(1,99)
                task={'summary':None if missing else f'delta={value}',
                      'measurements':{'delta':value}}
                truth=int(value>0)
            elif self.name == 'perfflux-sandbox':
                # Choose the lower simulated latency, including cache misses.
                hits=rng.choice((0.,.25,.5,.75,1.)); count=rng.randint(1,9)
                task={'request_count':count,'cache_hit_fraction':hits,
                      'direct_ms_per_request':8,'batch_overhead_ms':12,
                      'cache_miss_ms':10,'summary_available':not missing}
                truth=int(12+count*(1-hits)*10 < count*8)
            else:
                # Synthetic literature metadata relevance, not patient outcomes.
                relevant=bool(rng.getrandbits(1))
                task={'query_term':'marker-k',
                      'title':'marker-k study' if relevant and not missing else 'method study',
                      'abstract':'marker-k measured' if relevant else 'unrelated measurement',
                      'summary_available':not missing}
                truth=int(relevant)
            rows.append({'id':str(i),'cluster':'missing-context' if missing else 'simple',
                         'task':task,'truth':truth,'safety':i%11==0})
        return rows

    def public_input(self, item):
        # Allowlist: evaluator labels, safety strata and failure clusters never
        # reach skill code. JSON copying prevents mutation of evaluation input.
        import json
        return {'id':item['id'],'task':json.loads(json.dumps(item['task']))}

    def predict(self, skill, public):
        if set(public) != {'id','task'}:
            raise ValueError('predict accepts public task inputs only')
        if skill == 'always-abstain':
            return None
        if skill == 'random':
            return random.Random('registered-control:'+public['id']).randrange(2)
        if skill not in (*self.skills, 'candidate:context'):
            raise ValueError('unknown sandbox skill')
        task=public['task']; incumbent=skill==self.skills[0]
        if self.name == 'scientific':
            if incumbent:
                return None if task['summary'] is None else int(int(task['summary'].split('=')[1])>0)
            return int(task['measurements']['delta']>0)
        if self.name == 'perfflux-sandbox':
            if incumbent and not task['summary_available']:
                return None
            direct=task['request_count']*task['direct_ms_per_request']
            cached=task['batch_overhead_ms']+task['request_count']*(1-task['cache_hit_fraction'])*task['cache_miss_ms']
            return int(cached<direct)
        if incumbent and not task['summary_available']:
            return None
        text=task['title'] if incumbent else task['abstract']
        return int(task['query_term'] in text.split())

    def correct(self, prediction, item):
        return prediction == item['truth']

    def stream(self, size=1200):
        if size != 1200:
            raise ValueError('registered drift design has exactly 1200 items')
        a,b=self.skills
        rows=[]
        for i in range(size):
            phase=i//300
            rewards={a:phase in (0,3), b:phase in (1,2)}
            # Hardened B changes paired discordance and abstention telemetry.
            if phase==2 and i%4==0:
                rewards[a]=True
            rows.append({'id':str(i),'rewards':rewards,
                         'abstention':phase==2,'degraded':450<=i<510})
        return rows

DOMAINS={
    'scientific':Domain('scientific',('synthetic-family-a','synthetic-family-b')),
    'perfflux-sandbox':Domain('perfflux-sandbox',('direct','cached-batch')),
    'clinicalos-sandbox':Domain('clinicalos-sandbox',('title-retrieval','abstract-retrieval')),
}

def get_domain(domain):
    if isinstance(domain,Domain):
        if type(domain) is not Domain or domain != DOMAINS.get(domain.name):
            raise ValueError('unregistered custom domain contract; register implementation before evaluation')
        return domain
    try:
        return DOMAINS[domain]
    except KeyError as error:
        raise ValueError('unknown domain') from error
