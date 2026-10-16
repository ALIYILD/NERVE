# Sequential gate v2: prospective power feasibility

**The original simulation remains a negative power result: zero of 100 good
proposals accepted.** Its code, registration, wallet and receipts are unchanged.
The original nominal harmful/items target does not establish useful promotion.

A prospective usefulness requirement is at least 80% good acceptance in
expectation: four out of five beneficial proposals should survive the gate.
This is an explicit design target, not a clinical standard. Before generating
any new validation data, we checked whether increasing the item cap alone could
meet that requirement while keeping the equal alpha-wallet allocation and using
fewer than the current comparator's 20,000 items on average.

**It cannot within the existing fixed-bet/futility family.** The 100 good
proposals alone require at least **26,103.7 expected items**, even granting the
40 harmful and 60 neutral proposals zero cost. No additional empirical study
was run to try to obtain a lucky favorable seed.

## Assumptions and derivation

The sequential arm's fresh score-level fixture is unchanged: independent candidate correctness with
probability 0.65 and incumbent correctness with probability 0.5. A paired win
has probability 0.325, loss 0.175, and tie 0.5. The registered process multiplies
E by 1.3, 0.7, or 1 respectively. The expected log increment per item is

`mu = .325 log(1.3) + .175 log(.7) = 0.0228502707626564`.

The equal allocation is alpha=0.05/200=0.00025, so promotion requires
`log(E) >= A = log(4000) = 8.29404964010203`. Futility stops when E<=0.05.
Before every continuing step, log(E)>log(0.05). The smallest next increment is
log(0.7), so every terminal nonpromotion has

`log(E_T) >= L = log(.05) + log(.7) = -3.35240721749272`.

This includes stopping for item budget, plateau, or an additional stratum/domain
veto. Such vetoes cannot make the process continue beyond its first futility
crossing. An initial zero-item stop also satisfies the floor. Promotion is
bounded below by A. For good-acceptance probability q, it follows that

`E[log(E_T)] >= q A + (1-q) L`.

For any bounded stopping time under the IID paired fixture, each next primary
log increment has expectation mu conditional on the full previous history.
Therefore the stopped-sum identity gives `E[log(E_T)] = mu E[T]`. The argument
does not require the gate to discard candidate/incumbent information in ties;
additional vetoes may inspect that information. Combining the two statements,

`E[T_good] >= (q A + (1-q) L) / mu`.

At q=0.8 this is **261.036656 items per good proposal**. Across 100 good
proposals, the lower bound is **26,103.665600 items**. The bound is linear in q,
so q may also denote mean acceptance across those 100 good proposals. This already exceeds the
20,000-item total comparator budget before any null-proposal cost. Even with
zero cost for nulls, 20,000 expected items yields an optimistic upper bound of
**68.0246% expected good acceptance** in this family.

## Scope and decision

This is an expectation bound for the current bet, alpha allocation, futility
threshold, IID fixture, and bounded stopping. It covers any item-cap adjustment
and additional vetoes with those rules. It is not a universal impossibility
result for all sequential tests, other alpha allocations, or richer models.
A fortunate single finite run could satisfy the observed thresholds; that would
not invalidate the expectation bound. The analysis does not prove a population
harmful-accept rate below 1% from the original 0/40 observation.

A useful subsequent experiment must first change the proposed tradeoff or
register a genuinely different method. Merely raising the cap and searching
seeds is not a valid remedy. Neither the canonical gate nor the experimental
gate was changed. No alpha was weakened and no class labels were exposed to a
policy. There were no simulated outcome draws, model calls, or holdout accesses.

The derivation was performed exploratorily, then recorded in an exclusive
reproducibility registration before evaluating the formula in the standalone
script. This is **an analytical reproducibility check, not a preregistered
empirical confirmation**. Independent review checked the stopping floor and
conditional-increment argument before publication.

## Reproduction and receipts

```sh
python3 scripts/analyze_sequential_power_v2.py /absolute/new/output
```

Public artifacts: `evidence/sequential-power-feasibility-v2-registration.json`
and `evidence/sequential-power-feasibility-v2.json`.
Registration SHA-256:
`4e4ef2644d6f1b21378d6e37a55e2cbbf13dd530e334520c8f065236638a98ee`.
The script never reads the completed simulation outcomes. Original negative
result: [doc 85](85-sequential-gate.md).
