"""Fixed, synthetic comparison with the current slice decision (zero model calls)."""
from collections import Counter
from hashlib import sha256
from pathlib import Path
import random

from .sequential_gate_contract import canonical, plateau_minimum
from .sequential_gate_v1 import Gate

# Fixed before the first run. Outcomes are deliberately simple score-level fixtures,
# not scientific-task outputs or an empirical model of the seven-stratum bank.
DESIGN = dict(seed=20261015, proposals=200, harmful=40, items_per_proposal=100,
              harmful_win_probability=.45, beneficial_win_probability=.85,
              always_abstain_probability=.2, random_probability=.15,
              wallet_alpha=.05, study_alpha=.00025, bet=.5, futility_e=.05,
              dev_seed_deltas=[.38, .40, .42], strata=['s0', 's1', 's2', 's3', 's4'])
KEY = sha256(b'public synthetic integrity fixture, never a production key').digest()


def registration(index, design=DESIGN):
    rng = random.Random(design['seed'] + index)
    schedule = []
    for round_index in range(design['items_per_proposal']//len(design['strata'])):
        strata = design['strata'][:]; rng.shuffle(strata)
        schedule.extend(dict(item_id=f'{index}:{round_index}:{s}', stratum=s) for s in strata)
    return dict(study_id=f'synthetic-{index}', bank=dict(manifest='synthetic-bank-v1', split='synthetic'),
        candidate=f'candidate-{index}', incumbent='deployed-v3', deployed_incumbent='deployed-v3',
        reverted_only_candidate=True, mode='exploratory', dev_seed_deltas=design['dev_seed_deltas'], schedule=schedule,
        gate=dict(alpha=design['study_alpha'], bet=design['bet'], futility_e=design['futility_e'],
                  item_budget=design['items_per_proposal'], strata=design['strata'], order_seed=design['seed']+index,
                  minimum_net_wins=plateau_minimum(design['dev_seed_deltas'], design['items_per_proposal'])))


def slice_accept(rows):
    """Exact decision predicate of scientific_v3_holdout.aggregate, complete=True.

    100 paired items, five strata, 20 per stratum; candidate strictly beats all
    three arms globally and never scores below abstain within any stratum.
    Its Wilson intervals are descriptive, not part of the decision.
    """
    strata = {r['stratum'] for r in rows}
    return (len(strata) == 5 and all(sum(r['stratum']==s for r in rows)==20 for s in strata)
            and all(sum(r['candidate'] for r in rows) > sum(r[arm] for r in rows)
                    for arm in ('incumbent', 'always_abstain', 'random'))
            and all(sum(r['candidate']-r['always_abstain'] for r in rows if r['stratum']==s)>=0 for s in strata))


def simulate(directory):
    root = Path(directory); root.mkdir(parents=True, exist_ok=True)
    # Exclusive pre-registration creation before any outcome generation.
    with (root/'simulation-registration.json').open('x') as file:
        file.write(canonical(DESIGN)+'\n')
    rng = random.Random(DESIGN['seed'])
    harmful = set(rng.sample(range(DESIGN['proposals']), DESIGN['harmful']))
    gate = Gate(root/'private', key=KEY, total_alpha=DESIGN['wallet_alpha'])
    metrics = {name:dict(harmful_accepted=0, beneficial_accepted=0, items_consumed=0)
               for name in ('current_slice', 'sequential')}
    reports = []; verdicts = Counter()
    for index in range(DESIGN['proposals']):
        reg = registration(index); gate.start(reg)
        probability = DESIGN['harmful_win_probability'] if index in harmful else DESIGN['beneficial_win_probability']
        rows = []
        for item in reg['schedule']:
            candidate = rng.random() < probability
            rows.append(dict(item, candidate=candidate, incumbent=not candidate,
                             always_abstain=rng.random()<DESIGN['always_abstain_probability'],
                             random=rng.random()<DESIGN['random_probability']))
        current = slice_accept(rows)
        for row in rows:
            if gate.report(reg['study_id'])['verdict'] != 'running': break
            gate.claim(reg['study_id'], row['item_id'], row['stratum'])
            gate.record(reg['study_id'], row['item_id'], candidate=row['candidate'], incumbent=row['incumbent'],
                        controls={a:row[a] for a in ('always_abstain', 'random')}, violations=[])
        report = gate.report(reg['study_id']); reports.append(report); verdicts[report['verdict']] += 1
        for name, accepted, consumed in [('current_slice', current, len(rows)),
                ('sequential', report['verdict']=='exploratory_only', report['items'])]:
            m = metrics[name]; m['items_consumed'] += consumed
            m['harmful_accepted' if index in harmful else 'beneficial_accepted'] += int(accepted)
    ledger_head = gate.ledger_head(); gate.close()
    gate = Gate(root/'private', key=KEY, total_alpha=DESIGN['wallet_alpha'])
    replay = [gate.report(f'synthetic-{index}') for index in range(DESIGN['proposals'])]
    gate.close()
    for m in metrics.values():
        m['harmful_accept_rate'] = m['harmful_accepted']/DESIGN['harmful']
        m['beneficial_accept_rate'] = m['beneficial_accepted']/(DESIGN['proposals']-DESIGN['harmful'])
    return dict(version='loop40.2-staged-v1', design_sha256=sha256(canonical(DESIGN).encode()).hexdigest(),
                proposals=DESIGN['proposals'], harmful_proposals=DESIGN['harmful'], **metrics,
                sequential_verdicts=dict(verdicts), ledger_head=ledger_head,
                byte_identical_restart=canonical(reports)==canonical(replay), model_calls=0,
                holdout_accessed=False, production_authorized=False,
                target_met=metrics['sequential']['harmful_accept_rate']<.01 and
                           metrics['sequential']['items_consumed']<metrics['current_slice']['items_consumed'],
                limitations=['Synthetic score-level demonstration, not an exact Lewis replication.',
                    'Identical paired streams per comparator; fresh independent items per proposal. No adaptive reuse.',
                    'Baseline reuses the current decision rule without a stream-wise alpha wallet; production slices remain single-use.',
                    '40 harmful trials cannot establish a population harmful-accept rate below 1%.',
                    'Anytime validity requires conditional null validity; arbitrary adaptive reuse is unsupported.',
                    'Live evaluator, reserve run and signed deployment remain out of scope.'])


def simulate_reused_slice(directory):
    """Supplemental unsafe same-bank baseline; NOT evidence of valid adaptive reuse."""
    design = dict(seed=20261015, proposals=200, harmful=40, bank_items=100,
                  incumbent_probability=.5, harmful_probability=.45, beneficial_probability=.85,
                  abstain_probability=.2, random_probability=.15, item_difficulty_amplitude=.1,
                  policy='reuse same bank and incumbent/control outcomes for all 200 proposals; no alpha wallet')
    root = Path(directory); root.mkdir(parents=True, exist_ok=True)
    with (root/'reused-registration.json').open('x') as file: file.write(canonical(design)+'\n')
    rng = random.Random(design['seed'])
    harmful = set(rng.sample(range(200), 40))
    bank = [dict(stratum=f's{i%5}', incumbent=rng.random()<.5,
                 always_abstain=rng.random()<.2, random=rng.random()<.15,
                 difficulty=rng.uniform(-.1, .1)) for i in range(100)]
    counts = dict(harmful_accepted=0, beneficial_accepted=0)
    for index in range(200):
        probability = .45 if index in harmful else .85
        rows = [dict(item, candidate=rng.random()<probability+item['difficulty']) for item in bank]
        counts['harmful_accepted' if index in harmful else 'beneficial_accepted'] += int(slice_accept(rows))
    return dict(design=design, design_sha256=sha256(canonical(design).encode()).hexdigest(), **counts,
                harmful_accept_rate=counts['harmful_accepted']/40, beneficial_accept_rate=counts['beneficial_accepted']/160,
                item_evaluations=20000, unique_items=100, model_calls=0, production_authorized=False,
                limitation='Supplemental reused-bank baseline. Different pairing/correlation from the primary matched-stream experiment; do not attribute its difference solely to the gate.')


if __name__ == '__main__':
    import argparse
    import time
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', help='new directory for preregistration and private synthetic ledger')
    parser.add_argument('--reused-slice', action='store_true')
    args = parser.parse_args()
    started = time.monotonic()
    result = simulate_reused_slice(args.directory) if args.reused_slice else simulate(args.directory)
    result['wall_seconds'] = time.monotonic()-started
    (Path(args.directory)/'aggregate-report.json').write_text(canonical(result)+'\n')
    print(canonical(result))
