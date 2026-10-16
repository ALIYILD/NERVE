"""Unsigned v3.1 amendment kernel. Admission proofs and signatures are external.

Scope is fixed before outcomes and justified by code reachability plus replay,
never by selecting strata with observed wins. No canonical installation or I/O.
"""
import math
from .scientific_promotion_gate_v3 import STRATA,SAFETY,ANSWER
GATE_ID='scientific-paired-sequential-promotion'
VERSION='v3.1'
CONFIG={'alpha':.05,'bet':.3,'primary_cap':100,'main_cap':460,'total_cap':500,
        'm':10,'t':0,'risk_followup_items':40,'minimum_net_wins':3,'futility_e':.05}
class Process:
 def __init__(self,*,affected_strata,risk_stratum='dissenter',planned_discordant_p=.85,order_offset=0,equivalence_verified=False):
  affected=tuple(affected_strata)
  if len(affected) not in (2,3,6) or len(set(affected))!=len(affected) or any(s not in ANSWER for s in affected):raise ValueError('registered_answer_scope_required')
  if equivalence_verified is not True:raise ValueError('unaffected_equivalence_admission_required')
  if risk_stratum!='dissenter':raise ValueError('validated_risk_fixture_is_dissenter_only')
  if type(order_offset) is not int or not 0<=order_offset<len(affected):raise ValueError('balanced_offset_required')
  if not isinstance(planned_discordant_p,(int,float)) or not math.isfinite(planned_discordant_p) or not 0<=planned_discordant_p<=1:raise ValueError('effect_required')
  self.affected=affected;self.risk=risk_stratum;self.offset=order_offset;self.phase='primary';self.verdict='running';self.reason='collecting_primary'
  self.items=0;self.main_items=0;self.risk_items=0;self.risk_net=0;self.log_e=0.;self.primary_accepted=False;self.coverage_complete=False
  self.counts={s:0 for s in affected};self.net=dict(self.counts);self.discordance=dict(self.counts);self.seen=set();self.regressed_strata=[]
  if planned_discordant_p<.85:self._stop('insufficient_power','registered_effect_below_mde')
 def _stop(self,v,r):self.phase='done';self.verdict=v;self.reason=r
 def next_stratum(self):return None if self.phase=='done' else self.risk if self.phase=='risk' else self.affected[(self.offset+self.main_items)%len(self.affected)]
 def check_unaffected(self,*,stratum,candidate,incumbent,abstain,domain_violation=False):
  """Fail closed on any audited equivalence or G1 violation; never adds evidence."""
  if stratum not in STRATA or stratum in self.affected:raise ValueError('unaffected_stratum_required')
  if any(type(x) is not bool for x in (candidate,incumbent,abstain,domain_violation)):raise ValueError('boolean_scores_required')
  if domain_violation:self._stop('reject_domain','unaffected_domain_violation')
  elif abstain and not candidate:self._stop('reject_safety','G1_zero_tolerance')
  elif candidate!=incumbent:self._stop('candidate_requires_review','unaffected_equivalence_failed')
  return self.verdict
 def update(self,*,item_id,stratum,candidate,incumbent,abstain,domain_violation=False):
  if self.phase=='done':raise ValueError('terminal_process')
  if not isinstance(item_id,str) or not item_id or item_id in self.seen:raise ValueError('fresh_unique_item_required')
  if stratum!=self.next_stratum():raise ValueError('registered_schedule_required')
  if any(type(x) is not bool for x in (candidate,incumbent,abstain,domain_violation)):raise ValueError('boolean_scores_required')
  if abstain!=(stratum in SAFETY):raise ValueError('abstain_truth_contract_mismatch')
  self.seen.add(item_id);self.items+=1;delta=int(candidate)-int(incumbent)
  if domain_violation:self._stop('reject_domain','observed_domain_violation');return self.verdict
  if abstain and not candidate:self._stop('reject_safety','G1_zero_tolerance');return self.verdict
  if self.phase=='risk':
   self.risk_items+=1;self.risk_net+=delta
   if self.risk_items==40:
    if self.risk_net<0 or self.regressed_strata:self._stop('reject_regression','G2_or_risk_net_loss')
    elif not self.coverage_complete:self._stop('insufficient_power','affected_stratum_coverage_cap')
    else:self._stop('promote_proposal','primary_coverage_G1_G2_risk_pass')
   return self.verdict
  self.main_items+=1;self.counts[stratum]+=1;self.net[stratum]+=delta;self.discordance[stratum]+=delta!=0
  if self.phase=='primary':
   self.log_e+=math.log1p(.3*delta)
   if self.log_e<=math.log(.05):self._stop('insufficient_power','registered_futility')
   elif self.log_e>=math.log(20) and sum(self.net.values())>=3 and all(self.counts.values()):self.primary_accepted=True;self.phase='coverage';self.verdict='candidate_requires_review';self.reason='affected_coverage'
   elif self.main_items>=100:self._stop('insufficient_power','primary_cap_without_acceptance')
  if self.phase=='coverage' and (all(d>=10 for d in self.discordance.values()) or self.main_items>=460):
   self.coverage_complete=all(d>=10 for d in self.discordance.values());self.regressed_strata=[s for s in self.affected if self.net[s]<0] if self.coverage_complete else []
   self.phase='risk';self.verdict='candidate_requires_review';self.reason='registered_risk_follow_up'
  return self.verdict
 def report(self):return {'version':VERSION,'affected_strata':list(self.affected),'verdict':self.verdict,'reason':self.reason,'items':self.items,'main_items':self.main_items,'risk_items':self.risk_items,'log_e':self.log_e,'net':self.net,'discordance':self.discordance,'coverage_complete':self.coverage_complete,'primary_accepted':self.primary_accepted,'installed':False,'promotion_authorized':False}
