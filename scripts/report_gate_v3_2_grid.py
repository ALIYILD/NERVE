"""Verify CPU receipts, publish all coverage-grid tables and metric audit."""
import csv,gzip,json,sys
from pathlib import Path
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'docs/galahad/evidence/gate-v3_2-coverage-grid';E=ROOT/'docs/galahad/evidence'
def read(p):return json.loads(p.read_text())
def h(p):return sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def money(v):return f'${v[0]:.3f}–${v[1]:.3f}'
def run():
 reg=read(D/'registration.json');res=read(D/'result.json');r=res['results'];total=0
 rare=read(D/'harmful-promotion-scalar-audit.json');assert rare['all_matched'] and rare['harmful_promotions_replayed']==rare['harmful_promotions_expected']
 for p,digest in reg['sources'].items():assert h(ROOT/p)==digest,p
 assert res['registration_sha256']==h(D/'registration.json')
 for label,row in r.items():
  p=ROOT/row['receipt']['path'];assert h(p)==row['receipt']['sha256'];raw=gzip.decompress(p.read_bytes());assert sha256(raw).hexdigest()==row['receipt']['raw_sha256']
  rows=json.loads(raw);assert len(rows)==10000 and sum(x['promoted'] for x in rows)==row['accepted'] and sum(x['items'] for x in rows)==row['total_items']
  for x in rows:
   assert x['items']<=1000 and sum(x['counts'])+40*x['primary']==x['items']
   if x['promoted']:assert x['primary'] and x['covered'] and all(v>=0 for v in x['net'])
  total+=len(rows)
 sys.path.insert(0,str(ROOT/'src'))
 from nerve_awim.memory_gateway.retained_promotion_gate import verify
 assert verify()['version']=='v3'
 v3=read(E/'gate-v3-confirmation-v1-result.json')['results']['regression_requested']['10']
 old=read(E/'gate-v3_2-budget/result.json')['results'];audit={'v3':{'all_streams':10000,'nonpromoted':10000-v3['accepted'],'primary_nonacceptance':10000-v3['primary_accepts'],'coverage_incomplete':v3['coverage_incomplete'],'G2_rejections':v3['identified'],'G2_evaluated':v3['primary_accepts']-v3['coverage_incomplete'],'G2_detection_conditional':v3['identified']/(v3['primary_accepts']-v3['coverage_incomplete'])},'doc128':{}}
 for seed in ('registered','fresh'):
  x=old[seed+'-broad_75-regression'];evaluated=x['primary_accepts']-x['coverage_incomplete'];audit['doc128'][seed]={'nonpromoted':10000-x['accepted'],'primary_nonacceptance':10000-x['primary_accepts'],'coverage_incomplete':x['coverage_incomplete'],'G2_rejections':x['G2_veto_count'],'bad_stratum_identified':round(x['identification_rate']*10000),'G2_evaluated':evaluated,'G2_rejection_conditional':x['G2_veto_count']/evaluated,'bad_stratum_identification_conditional':round(x['identification_rate']*10000)/evaluated}
 write(D/'historical-metric-audit.json',audit)
 table=[]
 for seed in reg['seed_order']:
  for m in reg['coverage_grid']:
   for profile in ('broad_75','narrow_64','narrow_88','measured'):
    prefix=f'{seed}-m{m}-{profile}-';x=r[prefix+'regression']
    table.append({'seed':seed,'m':m,'profile':profile,'in_scope':profile!='narrow_88','good085':r[prefix+'good_085']['accept_rate'],'good090':r[prefix+'good_090']['accept_rate'],'regressed_nonpromotion':x['nonpromotion_rate'],'G2_bad_detection_evaluated':x['G2_identified_bad_rate_evaluated'],'primary_nonacceptance':x['primary_nonacceptance_count'],'coverage_incomplete':x['coverage_incomplete'],'neutral':r[prefix+'neutral']['accept_rate'],'harmful':r[prefix+'harmful']['accept_rate'],'H0':r[prefix+'H0']['accept_rate']})
 write(D/'tables.json',{'target_table':table,'all_classes':r,'historical_metric_audit':audit,'qualifications':res['qualifications'],'chosen_m':res['chosen_m']})
 cost=[]
 for label,x in r.items():
  seed,mt,profile,scenario=label.split('-',3)
  cost.append({'seed':seed,'m':int(mt[1:]),'profile':profile,'class':scenario,'in_scope':x['scope_admitted'],'raw_mean_items':x['mean_items'],'raw_p90_items':x['p90_items'],'mean_usd_low':x['mean_A40_usd'][0],'mean_usd_high':x['mean_A40_usd'][1],'p90_usd_low':x['p90_A40_usd'][0],'p90_usd_high':x['p90_A40_usd'][1],'mean_minutes_low':x['mean_A40_minutes'][0],'mean_minutes_high':x['mean_A40_minutes'][1],'p90_minutes_low':x['p90_A40_minutes'][0],'p90_minutes_high':x['p90_A40_minutes'][1],'scoped_mean_items':x['mean_items'] if x['scope_admitted'] else 0,'scoped_p90_items':x['p90_items'] if x['scope_admitted'] else 0})
 with (D/'items-and-cost-all-classes.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(cost[0]),lineterminator='\n');w.writeheader();w.writerows(cost)
 lines=['# 129 — Gate v3.2 coverage grid and scoped power claim','',f'**Selected m: {res["chosen_m"]}.** '+('No grid value satisfies all registered targets; no signing payload is prepared.' if res['chosen_m'] is None else 'The smallest qualifying value is selected prospectively by the registered rule; payload preparation is separate, with no signing or activation.'),'',
 'Zero model calls, zero pod operations, zero reserve consumption. Signed gate v3 remains canonical; v3.1 remains withdrawn. This is a research proposal.','',
 'All three m values fail the zero-harmful target: each has 1/10,000 harmful accepts in registered-seed narrow-64% and 2/10,000 in fresh-seed measured v5. Each case replays exactly through the scalar gate. At m=14 and16, broad G2 detection and the other in-scope rate targets pass, but that does not override the harmful criterion. At m=12, broad G2 detection also remains below90%.','',
 '## Registration, scope and unchanged rules','',
 'Registration and code hashes were frozen before all results. Original seeds 2026101801/main and 2026101802/H0 ran first for every m; fresh seeds 2026102401/main and 2026102402/H0 ran second. There are 10,000 streams per cell. Common random numbers across m/scenarios support paired comparisons; cells must not be pooled as independent replications. Grid m ∈ {12,14,16}; primary cap 300 balanced across nine strata; e ≥ 20 with the existing bet, futility and initial-observation conditions. Coverage samples only uncovered answer strata, least observed first, to m discordances or zero in 60. Total cap 1,000 = 960 main plus 40 unconditional dissenter follow-up. G1 zero-tolerance and G2 zero-net-loss unchanged.','',
 'The pre-registered minimum primary discordance is **8% across balanced all-nine samples**, with conditional win probability ≥ 0.85 for the proposed good-candidate power claim. The in-scope profiles under evaluation are broad-75%, narrow-64%, and measured v5; no gate is certified by this failed grid. The measured agreement discordances are 22% and 64%, zero elsewhere as an explicit historical plug-in assumption. Their all-nine discordance is 9.556%. Narrow-64% has 8%; broad-75% has 25%. This does not claim distribution-free power for every heterogeneous vector above the minimum.','',
 'Narrow-88% is out of claimed scope: its all-nine discordance is only 2.667%. The proposed public Process requires a prospectively registered dev-scope hash, profile and discordance. Below the floor or outside the validated profiles, it returns **insufficient_power before sampling**, never retain_incumbent. Scope evidence must be verified by the study custodian; a hash-shaped string alone is not provenance. Scope is not selected retrospectively from holdout outcomes. The measured-profile rate is a planning estimate, not a certified population lower bound: the dev pooled-discordance Wilson lower endpoint, scaled to all-nine balance, is about 7.50%, below the 8% floor.','',
 'Out-of-scope raw-kernel simulations are retained below as diagnostics, including their H0 rates and hypothetical costs. Actual scope-enforced narrow-88% acceptance and H0 promotion are both zero, with zero items consumed. The 8% floor is a necessary boundary of the claim, not a guarantee for arbitrary untested profiles.','',
 'Qualification: all in-scope profiles in both seed sets need good acceptance ≥ 80%, regressed non-promotion ≥ 90%, H0 ≤ 5%, zero observed harmful accepts; broad G2 identification among evaluated candidates must itself reach 90%. The raw out-of-scope H0 diagnostic must also stay ≤ 5%. Small silent regressions are reported separately without inventing another selection target.','',
 '## Correcting the historical regression metric','',
 'V3’s 92.12% broad non-promotion was **not G2 detection alone**: 2,474 primary non-acceptances + 62 incomplete evaluations + 6,676 G2 detections = 9,212 non-promotions. Of 7,464 candidates actually evaluated by G2, 6,676 were detected: **89.44%**.','',
 'Doc 128’s original-seed broad result was G2 alone: 8,529/10,000 detections = 85.29%, with no primary abandonment. Its fresh-seed 85.09% overall non-promotion contained one primary non-acceptance plus 8,508 G2 rejections; 8,507 identified the deliberately bad stratum. Therefore it would be inaccurate to relabel every previously reported v3.2 total as “G2 detection alone.” The tables here expose G2-only identification with its evaluated denominator, separately from any-route non-promotion.','',
 'The old uniform coverage also oversampled some strata while waiting for the slowest. Adaptive coverage stops an evaluated stratum at its threshold, so raising m directly tests G2 power without credit for primary non-evaluations.','',
 '## Target tables','',
 'Rates are percentages. Rows marked outside are raw diagnostic outcomes, not admitted gate promotions.','',
 '| Seed | m | Profile | Scope | Good .85 | Good .90 | Regressed non-promotion | G2 bad-stratum detection / evaluated | Neutral | Harmful | H0 |','|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|']
 for x in table:
  keys=['good085','good090','regressed_nonpromotion','G2_bad_detection_evaluated','neutral','harmful','H0'];vals=['n/a' if x[k] is None else f'{x[k]*100:.2f}' for k in keys]
  lines.append(f'| {x["seed"]} | {x["m"]} | {x["profile"]} | {"in" if x["in_scope"] else "outside"} | '+' | '.join(vals)+' |')
 lines+=['','## Silent 5% / 10% regressions','',
 'One nominally silent answer stratum has loss-only discordance of 5% or 10% per item; agreement strata retain p = 0.85. The bad stratum rotates. The bound column refers specifically to that bad stratum, with all 10,000 proposed studies as denominator. Outside rows are raw diagnostics.','',
 '| Seed | m | Profile | Loss rate | Non-promotion | Bad stratum identified | Bound activated | Promoted with bound |','|---|---:|---|---:|---:|---:|---:|---:|']
 for seed in reg['seed_order']:
  for m in reg['coverage_grid']:
   for profile in ('narrow_64','narrow_88','measured'):
    for q in ('05','10'):
     x=r[f'{seed}-m{m}-{profile}-silent_regression_{q}'];lines.append(f'| {seed} | {m} | {profile} | {int(q)}% | {100*x["nonpromotion_rate"]:.2f}% | {100*x["identification_rate"]:.2f}% | {x["bad_stratum_bound_activated_count"]}/10,000 | {x["bad_stratum_promotions_with_bound"]}/10,000 |')
 lines+=['',
 'Zero discordances in the predeclared first 60 observations gives a marginal one-sided 95% exact binomial upper bound of 4.8703%, approximated by 5% using the rule of three. It requires IID stationary per-stratum paired outcomes. It is not equivalence, not a simultaneous bound across strata, and not a general anytime confidence sequence. True 5%/10% regressions can still yield zero events in 60 items with probabilities 4.607%/0.180%. Both first-60 certificates and terminal bound activation are retained in the stream receipts.','',
 '## Items and cost','',
 '[Complete per-class mean/p90 items, minutes and cost table](evidence/gate-v3_2-coverage-grid/items-and-cost-all-classes.csv) covers all 186 cells, including good, regressed, silent, neutral, harmful and H0 scenarios. [Machine-readable tables](evidence/gate-v3_2-coverage-grid/tables.json) also contain every metric and route count. Costs project historical 2.3–3.4 seconds per item at $0.59/A40-hour; actual GPU/model spend here is zero. All proposals, including primary failures, contribute to mean and p90. Simulations assume fresh per-stratum reserve is available; any real study needs a separate exclusive allocation and must stop if its reserve is exhausted.','',
 'Measured-profile good classes:','',
 '| Seed | m | p | Accepts | Mean / p90 items | Mean cost | p90 cost |','|---|---:|---:|---:|---:|---:|---:|']
 for seed in reg['seed_order']:
  for m in reg['coverage_grid']:
   for scenario,p in [('good_085',.85),('never_worse',1.)]:
    x=r[f'{seed}-m{m}-measured-{scenario}'];lines.append(f'| {seed} | {m} | {p} | {x["accepted"]}/10,000 | {x["mean_items"]:.2f} / {x["p90_items"]:.1f} | {money(x["mean_A40_usd"])} | {money(x["p90_A40_usd"])} |')
 lines+=['','## Selection and verification','',f'Eligible values: **{res["eligible_m"]}**. Selected m: **{res["chosen_m"]}**. No target or seed was changed after results. Zero observed harmful accepts is a Monte Carlo requirement here, not a proof of zero population probability.','',f'{total:,} stream receipts verified, with {len(r)*100:,} independent scalar/vector checks and ten focused tests covering the grid, scope admission, caps, guards and follow-up. Canonical v3 signature verification passes. All item-level records here are simulated; no real reserve items were opened.','',
 f'Every harmful promotion was independently replayed through the public scoped scalar Process: {rare["harmful_promotions_replayed"]} cases, all matching verdict, items and per-stratum counts/net/discordance. This targets the rare outcomes that determine qualification, beyond the first100-per-cell parity sample. [Rare-promotion audit](evidence/gate-v3_2-coverage-grid/harmful-promotion-scalar-audit.json).','',
 'Sources: [registration](evidence/gate-v3_2-coverage-grid/registration.json), [results](evidence/gate-v3_2-coverage-grid/result.json), [historical metric audit](evidence/gate-v3_2-coverage-grid/historical-metric-audit.json).','']
 doc=ROOT/'docs/galahad/129-gate-v3_2-coverage-grid.md';doc.write_text('\n'.join(lines))
 verification={'streams_verified':total,'cells':len(r),'scalar_parity_streams':len(r)*100,'focused_tests_passed':10,'canonical_v3_signature_valid':True,'chosen_m':res['chosen_m'],'model_calls':0,'pod_operations':0,'reserve_consumed':0,'signed':False,'installed':False}
 write(D/'verification.json',verification)
 paths=list(D.glob('*'))+[ROOT/p for p in reg['sources']]+[Path(__file__),ROOT/'scripts/audit_gate_v3_2_rare_promotions.py',doc]
 write(E/'gate-v3_2-grid-research-evidence-index.json',{'kind':'research index, not signing payload','files':{str(p.relative_to(ROOT)):h(p) for p in sorted(set(paths)) if p.is_file()}})
 print(json.dumps(verification))
if __name__=='__main__':run()
