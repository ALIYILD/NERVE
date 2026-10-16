"""Verify and publish completed CPU simulation receipts; no inference."""
import json, gzip, sys
from pathlib import Path
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'docs/galahad/evidence/gate-v3_2-budget'
def read(p):return json.loads(p.read_text())
def h(p):return sha256(p.read_bytes()).hexdigest()
def money(x):return f'${x[0]:.3f}–${x[1]:.3f}'
def run():
 reg=read(D/'registration.json');result=read(D/'result.json');r=result['results'];streams=0
 assert result['registration_sha256']==h(D/'registration.json')
 for path,digest in reg['sources'].items():assert h(ROOT/path)==digest,path
 for label,row in r.items():
  p=ROOT/row['receipt']['path'];assert h(p)==row['receipt']['sha256'];raw=gzip.decompress(p.read_bytes());assert sha256(raw).hexdigest()==row['receipt']['raw_sha256']
  rows=json.loads(raw);assert len(rows)==10000 and sum(x['promoted'] for x in rows)==row['accepted']
  assert sum(x['items'] for x in rows)==row['total_items'] and max(x['items'] for x in rows)<=800
  for x in rows:
   assert sum(x['counts'])+40*x['primary']==x['items']
   if x['promoted']:assert x['covered'] and x['primary'] and all(v>=0 for v in x['net'])
  streams+=len(rows)
 sys.path.insert(0,str(ROOT/'src'))
 from nerve_awim.memory_gateway.retained_promotion_gate import verify
 proof=verify();assert proof['version']=='v3'
 lines=['# 128 — Gate v3.2 budget revision: primary 300, targeted coverage, cap 800','',
 '**Targets fail; no signing payload is prepared. Research proposal only.** All requested profiles were simulated, with zero model calls, no pod operations and no reserve access. No signature, installation or retention occurred. The canonical gate remains signed v3. Historical v3.1 remains withdrawn.','',
 '## Frozen design and execution','',
 'The [registration](evidence/gate-v3_2-budget/registration.json) was source-hashed before any simulation results. Original seeds 2026101801 (main) and 2026101802 (H0) ran first. New seeds 2026102301 and 2026102302 ran second, with no intervening tuning. Every cell contains 10,000 streams.','',
 'Primary sampling remains balanced across all nine strata, with e ≥ 20 or a 300-item cap. The existing bet 0.3, futility e ≤ 0.05, minimum net wins 3 and all-nine-observed conditions are retained. Acceptance is latched: coverage outcomes do not update the pooled e-process or rescue a failed primary stage.','',
 'After primary acceptance, sample only uncovered answer strata, selecting the least-observed first and resolving equal counts by the pre-registered rotated answer order. Primary observations count toward coverage. Coverage is ≥ 10 discordances OR zero discordances in ≥ 60 observations. A covered stratum drops out. Main sampling is capped at 760, reserving 40 unconditional dissenter follow-up items inside the 800 total cap. G1 is zero-tolerance; G2 is a single-stage zero-net-loss guard on complete coverage. Incomplete coverage gives insufficient_power.','',
 'G1 uses the recorded v3/v4 zero-misfire fixture; its false-veto rate is zero in this simulation, not a population safety guarantee. The dissenter follow-up remains structural both-correct ties under that fixture.','',
 'Broad 75% ties means 75% overall across nine strata, hence 37.5% discordance within each of six answer strata, matching historical simulations. Narrow 64%/88% ties are within the two agreement strata; all other strata are structural ties in those fixtures. The measured profile uses agreement discordance 22% and 64%, separately; zero elsewhere is the historical plug-in assumption, not proof.','',
 'The regressed alternative sets one active answer stratum to p = 0.30 among discordances and the other active strata to 0.91875. The bad stratum rotates. This has a different pooled effect in two-active and six-active fixtures; no claim of equal pooled effect is made. Neutral/H0 use p = 0.5; harmful uses p = 0.35.','',
 'Qualification requires good acceptance ≥ 80% at p = 0.85, regressed non-promotion ≥ 90%, H0 false promotion ≤ 5%, and zero observed harmful accepts, in every profile in both seed sets. No averaging across profiles. These are Monte Carlo point estimates; zero observed harmful accepts is not a proof of zero population probability.','',
 '## Target table','',
 'Percentages; regressed means non-promotion by any route, not localization.','',
 '| Seeds | Profile | Good .85 | Good .90 | Regressed non-promotion | Neutral accept | Harmful accept | H0 promotion | Pass all |',
 '|---|---|---:|---:|---:|---:|---:|---:|---|']
 for seed in reg['seed_order']:
  for name in ('broad_75','narrow_64','narrow_88','measured'):
   prefix=f'{seed}-{name}-'
   def v(s,k='accept_rate'):return 100*r[prefix+s][k]
   lines.append(f'| {seed} | {name} | {v("good_085"):.2f} | {v("good_090"):.2f} | {v("regression","nonpromotion_rate"):.2f} | {v("neutral"):.2f} | {v("harmful"):.2f} | {v("H0"):.2f} | {result["qualifications"][prefix[:-1]]} |')
 lines+=['','The adaptive budget fixes silent-stratum coverage and gives the measured pair adequate simulated power. It does not qualify the general design: the broad regressed alternative is promoted about 15% of the time, the narrow 88%-tie primary remains unpowered, and the narrow 64%-tie harmful class has one acceptance in each seed set. Extending the primary stage removes some non-promotions that previously contributed to the regression metric; unchanged G2 at ten discordances does not compensate in the broad fixture. No thresholds or sample sizes were tuned after observing this.','', '## Measured pair, p = 1.0 and p = 0.85','', '| Seeds | Conditional p | Accepts /10,000 | Primary accepts | Incomplete coverage | Mean / p90 items | Mean cost | p90 cost |','|---|---:|---:|---:|---:|---:|---:|---:|']
 for seed in reg['seed_order']:
  for scenario,p in [('never_worse',1.),('good_085',.85)]:
   x=r[f'{seed}-measured-{scenario}'];lines.append(f'| {seed} | {p} | {x["accepted"]} | {x["primary_accepts"]} | {x["coverage_incomplete"]} | {x["mean_items"]:.2f} / {x["p90_items"]:.1f} | {money(x["mean_A40_usd"])} | {money(x["p90_A40_usd"])} |')
 lines+=['','## Silent-stratum regressions and bound activation','',
 'A nominally silent answer stratum has 5% or 10% loss-only discordance per item; the two active agreement strata retain p = 0.85. The selected silent stratum rotates across the four otherwise silent answer strata. These are absolute per-item regressions, not reductions in conditional win probability.','',
 'Bound activation below refers specifically to the deliberately regressed stratum, not the other genuinely silent strata. First-60 certificates and terminal silent coverage are separately recorded in every stream. Rates use all 10,000 proposed studies as denominator, including primary failures.','',
 '| Seeds | Profile | Silent loss | Non-promotion | Identified | First-60 certificates | Terminal bound activated | Promotions with that bound |','|---|---|---:|---:|---:|---:|---:|---:|']
 for seed in reg['seed_order']:
  for name in ('narrow_64','narrow_88','measured'):
   for suffix in ('05','10'):
    x=r[f'{seed}-{name}-silent_regression_{suffix}'];lines.append(f'| {seed} | {name} | {int(suffix)}% | {100*x["nonpromotion_rate"]:.2f}% | {100*x["identification_rate"]:.2f}% | {x["bad_stratum_first60_certificate_count"]}/10,000 | {x["bad_stratum_bound_activated_count"]}/10,000 | {x["bad_stratum_promotions_with_bound"]}/10,000 |')
 lines+=['',
 'When the silent branch activates, the stated upper bound is approximately 5% (rule of three), or exactly 4.8703% at one-sided 95% confidence for a fixed first 60 IID stationary per-stratum paired outcomes. It is a marginal incidence bound, not equivalence, not a simultaneous guarantee across strata and not a general anytime confidence sequence. The probability of zero observations of a real 5%/10% loss process in 60 items is 4.607%/0.180%, before accounting for the chance the study reaches those 60 items. A true small regression can therefore activate the bound and occasionally be promoted. If fewer than 60 observations are collected, no such bound is stated.','',
 '## Items and projected cost for every class','',
 'All proposals are included, including failed primary stages and follow-ups. Dollar ranges use historical 2.3–3.4 seconds per item and A40 $0.59/hour. These are hypothetical all-arm study projections, not billed simulation costs; this work used zero GPU/model calls. Machine-readable results also include mean/p90 minutes.','',
 '| Seeds | Profile | Class | Mean items | p90 items | Mean cost | p90 cost |','|---|---|---|---:|---:|---:|---:|']
 for seed in reg['seed_order']:
  for name in ('broad_75','narrow_64','narrow_88','measured'):
   for scenario in ('good_085','good_090','never_worse','regression','neutral','harmful','H0','silent_regression_05','silent_regression_10'):
    key=f'{seed}-{name}-{scenario}'
    if key not in r:continue
    x=r[key];lines.append(f'| {seed} | {name} | {scenario} | {x["mean_items"]:.2f} | {x["p90_items"]:.1f} | {money(x["mean_A40_usd"])} | {money(x["p90_A40_usd"])} |')
 lines+=['','## Verification and disposition','',
 f'{streams:,} simulated streams across {len(r)} cells were verified against receipt hashes and aggregate counts. Each cell includes 100 independent scalar/vector parity checks, {len(r)*100:,} total, covering scheduling, counts, discordance, net, primary acceptance, coverage, promotion and items. Six focused tests passed for primary cap, total cap including follow-up, adaptive silent coverage, branch boundaries, G1, G2 and follow-up safety. Canonical v3 signature verification passes.','',
 f'All target cells qualify: **{result["all_targets_pass"]}**. '+('A payload requires a separate preparation step; no signature is authorized.' if result['all_targets_pass'] else '**No signing payload is prepared.** The failed profiles and measured-pair reachability are preserved without changing the gate after observing them.'),'',
 'Evidence: [registration](evidence/gate-v3_2-budget/registration.json), [full results and compressed stream receipt hashes](evidence/gate-v3_2-budget/result.json). Real bank-v5 dev measurements remain those of [doc 127](127-bank-v5-dev-and-v3_2-measured-power.md); no new real data were consumed.','']
 doc=ROOT/'docs/galahad/128-gate-v3_2-budget-revision.md';doc.write_text('\n'.join(lines))
 receipt={'streams_verified':streams,'cells':len(r),'scalar_parity_streams':len(r)*100,'focused_tests_passed':6,'canonical_v3_signature_verified':True,'model_calls':0,'pod_operations':0,'reserve_consumed':0,'all_targets_pass':result['all_targets_pass'],'payload_prepared':False}
 writepath=D/'verification.json';writepath.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
 files=[doc,Path(__file__)]+[ROOT/p for p in reg['sources']]+list(D.glob('*'))
 index={'kind':'research evidence only, not a signing payload','files':{str(p.relative_to(ROOT)):h(p) for p in sorted(set(files)) if p.is_file()}}
 (ROOT/'docs/galahad/evidence/gate-v3_2-budget-evidence-index.json').write_text(json.dumps(index,indent=2,sort_keys=True)+'\n')
 print(json.dumps(receipt))
if __name__=='__main__':run()
