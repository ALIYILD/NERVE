#!/usr/bin/env python3
"""Reproduce a scoped Wald bound; no simulated outcomes or model calls.

The derivation was exploratory, before this reproducibility registration.
The exclusive registration freezes assumptions and formula before evaluation;
it is not a fresh empirical validation study or a claim of new learning.
"""
import argparse
from hashlib import sha256
import json
import math
from pathlib import Path

DESIGN=dict(version='sequential-power-feasibility-v2',study_kind='analytical_reproducibility',
    prior_derivation_disclosed=True,proposals=200,good_proposals=100,
    wallet_alpha=.05,equal_study_alpha=.00025,bet=.3,futility_e=.05,
    candidate_correct_probability=.65,incumbent_correct_probability=.5,
    candidate_incumbent_independent=True,primary_win_probability=.325,
    primary_loss_probability=.175,tie_probability=.5,
    required_expected_good_acceptance=.8,comparison_items=20000,
    threshold_rationale='Prospective usefulness criterion: retain at least four out of five genuinely beneficial proposals in expectation, unlike prior zero of 100. A design target, not a clinical or statistical standard.',
    assumption='IID primary paired outcomes conditional on full past; bounded stopping time; each processed item counted; no optional rejection causes primary log E to fall below its first-futility-crossing floor.',
    scope='Current fixed-bet/futility/equal-wallet family with arbitrary bounded item cap and additional vetoes; not all sequential gates.',
    formula='E[T_good] >= (q*log(1/alpha)+(1-q)*(log(futility_e)+log(1-bet)))/mu; mu=Pwin*log(1+bet)+Ploss*log(1-bet)',
    seed=None,random_draws=0,model_calls=0,
    original_evidence='docs/galahad/evidence/sequential-gate-sim-v1.json is immutable; its outcomes are not read by this calculation')


def canonical(value):return json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n'
def exclusive(path,value):
    with Path(path).open('x') as f:f.write(canonical(value))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    out=parser.parse_args().directory;out.mkdir(parents=True,exist_ok=True)
    registration=dict(design=DESIGN,source_sha256=sha256(Path(__file__).read_bytes()).hexdigest())
    exclusive(out/'registration.json',registration)
    d=DESIGN;b=d['bet'];q=d['required_expected_good_acceptance']
    mu=d['primary_win_probability']*math.log1p(b)+d['primary_loss_probability']*math.log1p(-b)
    upper=math.log(1/d['equal_study_alpha']);lower=math.log(d['futility_e'])+math.log1p(-b)
    bound=(q*upper+(1-q)*lower)/mu
    total=bound*d['good_proposals']
    result=dict(version=d['version'],registration_sha256=sha256((out/'registration.json').read_bytes()).hexdigest(),
        expected_primary_log_increment=mu,promotion_log_threshold=upper,
        terminal_nonpromotion_log_floor=lower,required_expected_good_acceptance=q,
        minimum_expected_items_per_good=bound,
        minimum_expected_items_for_good100_only=total,
        comparison_items=d['comparison_items'],expected_joint_targets_feasible_in_this_family=total<d['comparison_items'],
        null_proposal_item_cost_assumed_for_bound=0,
        optimistic_max_expected_good_acceptance_at20000=(mu*(d['comparison_items']/d['good_proposals'])-lower)/(upper-lower),
        additional_empirical_validation_run=False,random_draws=0,model_calls=0,
        interpretation='80% expected good acceptance needs at least 26103.7 expected items for the 100 good proposals alone; current fixed family cannot also average fewer than 20000 total items. No claim that a lucky finite realisation is impossible. No claim about other gates or alpha allocations.')
    exclusive(out/'result.json',result);print(canonical(result))

if __name__=='__main__':main()
