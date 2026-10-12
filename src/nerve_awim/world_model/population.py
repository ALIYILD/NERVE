"""Bounded competing declarative hypotheses; disagreement remains visible."""
import random
from .compiler import Simulator
from .contracts import digest
from .replay import replay


def select(programs, episodes, probes, *, seed=0, maximum=3):
    if type(maximum) is not int or not 1 <= maximum <= 3 or len(programs) > 3 or len(probes) > 100:
        raise ValueError('bounded population and probes required')
    survivors, seen = [], set()
    for program in programs:
        if not replay(program,episodes)['replay_pass']:
            continue
        sim = Simulator(program)
        behavior = [sim.step(sim.initialise(p['initial']),p['action']) for p in probes]
        signature = digest([{k:v for k,v in b.items() if k != 'rule_id'} for b in behavior])
        if signature not in seen:
            seen.add(signature)
            survivors.append(program)
    random.Random(seed).shuffle(survivors)
    return {'members':survivors[:maximum],'seed':seed,'status':'retained' if survivors else 'unknown'}


def disagreement(programs, initial, action):
    predictions = []
    for program in programs:
        sim = Simulator(program)
        state = sim.step(sim.initialise(initial),action)
        predictions.append({'observation':sim.observe(state),'goal':sim.goal(state)})
    return {'predictions':predictions,'disagrees':len({digest(x) for x in predictions}) > 1,
            'probe_permission':'simulation_only'}
