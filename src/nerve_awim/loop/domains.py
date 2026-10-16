"""Synthetic non-patient contracts; no remote model or real reward implied."""
from dataclasses import dataclass
import random

@dataclass(frozen=True)
class Domain:
    name: str
    skills: tuple[str,str]
    reward_source: str = 'synthetic ground truth'

    def bank(self, size=100):
        if type(size) is not int or not 1 <= size <= 12000:
            raise ValueError('bounded item budget required')
        return [{'id':str(i),'cluster':'missing-context' if i%3==0 else 'simple',
                 'truth':i%2,'safety':i%11==0} for i in range(size)]

    def predict(self, skill, item):
        if skill == self.skills[0]:
            return None if item['cluster']=='missing-context' else item['truth']
        if skill in (self.skills[1], 'candidate:context'):
            return item['truth']
        if skill == 'always-abstain':
            return None
        if skill == 'random':
            return random.Random('registered-control:'+item['id']).randrange(2)
        raise ValueError('unknown sandbox skill')

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
        return domain
    try:
        return DOMAINS[domain]
    except KeyError as error:
        raise ValueError('unknown domain') from error
