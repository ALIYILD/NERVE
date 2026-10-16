"""Full-information sandbox router over host-declared retained skills.

No installation or global promotion occurs. Scores require paired observations;
this is not a production contextual bandit with unobserved counterfactuals.
"""
from dataclasses import dataclass, field

@dataclass
class SiteRouter:
    retained: list
    current: str
    window: int = 20
    verification_window: int = 10
    margin: float = .2
    previous: str | None = None
    verifying: int = 0
    failures: int = 0
    history: list = field(default_factory=list)
    blocked: list = field(default_factory=list)
    cooldown: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.retained or len(set(self.retained)) != len(self.retained) or self.current not in self.retained:
            raise ValueError('current must belong to unique retained skills')
        if self.window < 2 or self.verification_window < 1 or not 0 < self.margin <= 1:
            raise ValueError('invalid router configuration')

    def update(self, rewards, served_correct=None, drift=False):
        if set(rewards) != set(self.retained) or any(type(x) is not bool for x in rewards.values()):
            raise ValueError('paired boolean rewards for retained skills required')
        if served_correct is not None and type(served_correct) is not bool:
            raise ValueError('boolean served outcome required')
        observed = rewards[self.current] if served_correct is None else served_correct
        events=[]
        self.history=(self.history+[dict(rewards)])[-self.window:]
        self.cooldown={s:n-1 for s,n in self.cooldown.items() if n>1}
        self.blocked=list(self.cooldown)
        # Canary safety is continuous, including after the initial verification.
        self.failures = self.failures+1 if not observed and (self.verifying or rewards[self.current]) else 0
        if self.previous is not None and self.failures >= 3:
            failed=self.current
            self.current,self.previous=self.previous,None
            self.blocked.append(failed)
            self.cooldown[failed]=60
            self.verifying=0
            self.failures=0
            events.append({'kind':'rollback','from':failed,'to':self.current})
            return events
        if self.verifying:
            self.verifying-=1
            if self.verifying==0:
                events.append({'kind':'verified','skill':self.current})
            return events
        if len(self.history)==self.window:
            scores={s:sum(row[s] for row in self.history)/self.window for s in self.retained}
            eligible=[s for s in self.retained if s not in self.blocked]
            best=max(eligible,key=lambda s:(scores[s],s)) if eligible else self.current
            if best != self.current and scores[best] >= scores[self.current]+self.margin:
                old=self.current
                self.previous,self.current=old,best
                self.verifying=self.verification_window
                self.failures=0
                events.append({'kind':'switch','from':old,'to':best,'scores':scores})
        return events
