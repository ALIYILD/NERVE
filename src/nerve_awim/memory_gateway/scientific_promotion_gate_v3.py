"""Unsigned proposed scientific promotion gate v3. No I/O or activation hooks.

MDE is prospective design eligibility, not knowledge of the true effect or an
observed-p cutoff. E evidence controls crossing; count guard is descriptive.
"""
import math
GATE_ID='scientific-paired-sequential-promotion'
VERSION='v3'
CONFIG={'alpha':.05,'bet':.3,'item_budget':100,'tie_probability_design':.75,
        'minimum_detectable_discordant_p':.85,'minimum_net_wins':3,
        'futility_e':.05,'stratum_net_loss_tolerance':0,'minimum_pairs_per_stratum':1}
POWER_EVIDENCE='docs/galahad/evidence/sequential-round2-v1-result.json'

class Process:
 def __init__(self,*,strata,planned_discordant_p,alpha=.05):
  if not strata or len(strata)>100 or len(set(strata))!=len(strata):raise ValueError('unique_bounded_strata_required')
  if type(planned_discordant_p) not in (int,float) or not math.isfinite(planned_discordant_p) or not 0<=planned_discordant_p<=1:raise ValueError('registered_effect_required')
  if type(alpha) not in (int,float) or not math.isfinite(alpha) or not 0<alpha<=.05:raise ValueError('bounded_alpha_required')
  self.strata=tuple(strata);self.alpha=alpha;self.planned_p=planned_discordant_p
  self.counts={s:dict(n=0,candidate_correct=0,incumbent_correct=0,abstain_correct=0,wins=0,losses=0) for s in strata}
  self.items=0;self.wins=0;self.losses=0;self.log_e=0.;self.seen=set()
  self.verdict='running';self.reason='collecting';self.power_citation=POWER_EVIDENCE+'#/power_100_items/1'
  if planned_discordant_p<.85:
   self.verdict='insufficient_power';self.reason='registered_effect_below_mde'
   self.power_citation=POWER_EVIDENCE+'#/power_100_items/0' # p=.65 illustrative weak-effect row; not interpolation
 def guard(self):
  return all(x['n']>=1 and x['candidate_correct']>=x['incumbent_correct'] and x['candidate_correct']>=x['abstain_correct'] for x in self.counts.values())
 def update(self,*,item_id,stratum,candidate,incumbent,abstain,domain_violation=False):
  if self.verdict!='running':raise ValueError('terminal_process')
  if not isinstance(item_id,str) or not item_id or item_id in self.seen:raise ValueError('fresh_unique_item_required')
  if stratum not in self.counts or any(type(x) is not bool for x in (candidate,incumbent,abstain,domain_violation)):raise ValueError('registered_stratum_boolean_scores_required')
  self.seen.add(item_id);self.items+=1;x=self.counts[stratum];x['n']+=1
  x['candidate_correct']+=candidate;x['incumbent_correct']+=incumbent;x['abstain_correct']+=abstain
  win=candidate and not incumbent;loss=incumbent and not candidate
  x['wins']+=win;x['losses']+=loss;self.wins+=win;self.losses+=loss
  self.log_e+=math.log1p(.3*(int(candidate)-int(incumbent)))
  if domain_violation:self.verdict='reject_domain';self.reason='observed_domain_violation'
  elif self.log_e<=math.log(.05):self.verdict='insufficient_power';self.reason='registered_futility'
  elif self.log_e>=-math.log(self.alpha) and self.wins-self.losses>=3 and self.guard():self.verdict='promote_proposal';self.reason='e_threshold_plateau_and_count_guard'
  elif self.items>=100:
   if not all(x['n'] for x in self.counts.values()):self.verdict='incomplete_infrastructure';self.reason='uncovered_strata'
   elif not self.guard():self.verdict='reject_regression';self.reason='observed_count_regression'
   else:self.verdict='insufficient_power';self.reason='item_budget_without_threshold'
  return self.verdict
 def report(self):
  return {'gate_id':GATE_ID,'version':VERSION,'verdict':self.verdict,'reason':self.reason,'items':self.items,
          'wins':self.wins,'losses':self.losses,'log_e':self.log_e,'alpha':self.alpha,
          'planned_discordant_p':self.planned_p,'power_citation':self.power_citation,
          'power_citation_note':'p=.65 row illustrates weak-effect design; p=.85 row is MDE upper-bound calculation, not a claim about unknown true p.',
          'strata':self.counts,'count_guard_passed':self.guard(),'tolerance':0,
          'promotion_authorized':False,'installed':False}

def promotion_authority(gate_version,*,signature_verified=False,active_version=None):
 # Decision adapter for the prospective policy; callers must supply verified trust.
 return signature_verified is True and active_version==VERSION and gate_version==VERSION
