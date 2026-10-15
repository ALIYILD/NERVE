#!/usr/bin/env python3
"""Fixed 200-proposal simulation; zero model calls and no canonical activation."""
from collections import Counter
from hashlib import sha256
import argparse
import importlib.util
import json
from pathlib import Path
import random
import time
from nerve_awim.memory_gateway.scientific_sequential_contract import canonical
from nerve_awim.memory_gateway.scientific_alpha_wallet import AlphaWallet
from nerve_awim.memory_gateway.scientific_sequential_gate import Gate

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('slice_comparator', ROOT/'scripts/run_scientific_runpod_gate.py')
SLICE = importlib.util.module_from_spec(spec); spec.loader.exec_module(SLICE)
DESIGN = dict(version='sequential-sim-v1', seed=20261016, proposals=200,
              classes={'harmful':40, 'neutral':60, 'good':100},
              discordant_win_probabilities={'harmful':.35,'neutral':.5,'good':.65},
              item_budget=100, strata=list(SLICE.gate.STRATA),
              total_alpha=.05, study_alpha=.00025, bet=.3, futility_e=.05,
              minimum_net_wins=3, robustness_seed_variance=0,
              abstain_probability=.2, random_probability=.15,
              arm_a='same 100 synthetic item/control identities across 200 proposals; no wallet',
              arm_b='fresh independent paired items per proposal; frozen wallet',
              matched_sensitivity='current slice predicate on the full fresh arm-B stream',
              pairing='independent candidate Bernoulli(p), incumbent Bernoulli(.5); discordant P(win)=p',
              caveat='A vs B differs in reuse and correlation; not a causal estimate of gate alone')
KEY = sha256(b'public synthetic journal test key, not operator credentials').digest()


def registration(index, design=DESIGN):
    rng = random.Random(design['seed']+index)
    schedule = []
    for r in range(design['item_budget']//len(design['strata'])):
        strata = list(design['strata']); rng.shuffle(strata)
        schedule.extend(dict(item_id=f'fresh-{index}-{r}-{s}', stratum=s) for s in strata)
    return dict(study_id=f'sim-{index}', bank=dict(manifest='synthetic-overnight-20261016', split='synthetic'),
                mode='exploratory', candidate=f'candidate-{index}', incumbent='synthetic-deployed-v1',
                deployed_incumbent='synthetic-deployed-v1', reverted_only_candidate=True,
                dev_seed_deltas=[0,0,0], schedule=schedule,
                gate=dict(alpha=design['study_alpha'], bet=design['bet'], futility_e=design['futility_e'],
                          minimum_net_wins=3, item_budget=design['item_budget'], strata=design['strata'],
                          order_seed=design['seed']+index))


def slice_accept(rows):
    expanded = []
    for row in rows:
        for arm, field in [('candidate','candidate'),('baseline','incumbent'),('always_abstain','always_abstain'),('random','random')]:
            expanded.append(dict(arm=arm,stratum=row['stratum'],score=dict(strict_correct=row[field],schema_valid=True)))
    return SLICE.aggregate(expanded, True)['verdict']=='promote_proposal'


def simulate(directory):
    root = Path(directory); root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.stat().st_mode & 0o077: raise ValueError('private_simulation_directory_required')
    source_paths = [Path(__file__), ROOT/'scripts/run_scientific_runpod_gate.py',
                    *sorted((ROOT/'src').rglob('*.py'))]
    prereg = dict(design=DESIGN, sources={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in source_paths})
    # Exclusive registration precedes wallet creation and all outcome generation.
    with (root/'registration.json').open('x') as f: f.write(canonical(prereg)+'\n')
    regs = [registration(i) for i in range(200)]
    wallet_path = root/'alpha-wallet.json'
    wallet_hash = AlphaWallet.create(wallet_path, regs)
    wallet = AlphaWallet(wallet_path, expected_sha256=wallet_hash)
    rng = random.Random(DESIGN['seed'])
    classes = [label for label,count in DESIGN['classes'].items() for _ in range(count)]; rng.shuffle(classes)
    # A fixed synthetic bank: reuse is deliberate and is NOT permitted by B's wallet.
    bank_a = [dict(stratum=s,incumbent=rng.random()<.5,always_abstain=rng.random()<.2,random=rng.random()<.15)
              for _ in range(20) for s in DESIGN['strata']]
    names = ('current_slice_naive_reuse','sequential_wallet','current_slice_fresh_matched')
    metrics = {name:dict(accepted={k:0 for k in DESIGN['classes']},items_consumed=0) for name in names}
    reports=[]; replay_ok=True
    for i,label in enumerate(classes):
        p = DESIGN['discordant_win_probabilities'][label]
        reused = [dict(row,candidate=rng.random()<p) for row in bank_a]
        rows = [dict(item,candidate=rng.random()<p,incumbent=rng.random()<.5,
                     always_abstain=rng.random()<.2,random=rng.random()<.15) for item in regs[i]['schedule']]
        gate = Gate(root/'journals'/f'sim-{i}',wallet=wallet,key=KEY); gate.start(regs[i])
        for row in rows:
            if gate.report(f'sim-{i}')['verdict'] != 'running': break
            gate.claim(f'sim-{i}',row['item_id'],row['stratum'])
            gate.record(f'sim-{i}',row['item_id'],candidate=row['candidate'],incumbent=row['incumbent'],
                        controls={a:row[a] for a in ('always_abstain','random')},violations=[])
        report = gate.report(f'sim-{i}'); head=gate.ledger_head(); gate.close()
        gate = Gate(root/'journals'/f'sim-{i}',wallet=wallet,key=KEY,expected_ledger_head=head)
        replay_ok &= gate.report(f'sim-{i}')==report; gate.close()
        reports.append(dict(study_id=f'sim-{i}',proposal_class=label,**report))
        for name,accept,n in [(names[0],slice_accept(reused),100),
                              (names[1],report['verdict']=='promote_proposal',report['items']),
                              (names[2],slice_accept(rows),100)]:
            metrics[name]['accepted'][label] += int(accept)
            metrics[name]['items_consumed'] += n
    wallet.verify()
    for m in metrics.values():
        for label,n in DESIGN['classes'].items(): m[label+'_accept_rate']=m['accepted'][label]/n
    result = dict(version=DESIGN['version'],registration_sha256=sha256((root/'registration.json').read_bytes()).hexdigest(),
                  wallet_sha256=wallet_hash,wallet_unchanged=True,wallet_alpha_reserved=.05,
                  model_calls=0,holdout_accessed=False,canonical_gate_changed=False,
                  replay_identical=replay_ok,metrics=metrics,proposals=200,
                  sequential_verdicts=dict(Counter(r['verdict'] for r in reports)),
                  target_met=metrics[names[1]]['harmful_accept_rate']<.01 and metrics[names[1]]['items_consumed']<20000,
                  harmful_zero_of_40_one_sided_95_upper=1-.05**(1/40),
                  unique_item_identities={names[0]:100,names[1]:metrics[names[1]]['items_consumed']},
                  limitations=['0/40 is not a population error rate below 1%.',
                    'Simulation inputs are score-level fixtures; no clinical or model evidence.',
                    'Fresh independent paired samples are required for conditional-null validity.',
                    'Non-crossing stratum veto does not establish noninferiority.',
                    'Power and good-accept rate must accompany harmful-accept and item savings.',
                    DESIGN['caveat']],studies=reports)
    (root/'result.json').write_text(canonical(result)+'\n')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('directory'); args=parser.parse_args()
    started=time.monotonic(); result=simulate(args.directory)
    print(canonical({k:v for k,v in result.items() if k!='studies'}))
    print('Wall seconds:',time.monotonic()-started)
