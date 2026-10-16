"""Unsigned gate v3.2 coverage-grid research proposal; never canonical. Pure scoring state; no activation or I/O.

Fresh-item conditional-null validity is required externally. A verified signature,
source/manifest binding and exclusive reserve admission remain separate duties.
"""
import math
GATE_ID='scientific-paired-sequential-promotion'
VERSION='v3.2'
STRATA=('supported-measurement','measurement-decoy','entity-decoy','unit-mismatch','conflict','multi-source-agreement','stale-vs-current','format-variant-agreement','dissenter')
SAFETY=frozenset(('unit-mismatch','conflict','dissenter'))
ANSWER=tuple(s for s in STRATA if s not in SAFETY)
CONFIG={'alpha':.05,'bet':.3,'primary_cap':300,'total_cap':1000,'main_cap':960,'risk_followup_items':40,
        'minimum_detectable_discordant_p':.85,'minimum_net_wins':3,'futility_e':.05,'stratum_net_loss_tolerance':0,
        'coverage_candidates':[12,14,16],'safety_tolerance':0,'fresh_items_only':True}
POWER_EVIDENCE='docs/galahad/evidence/gate-v3_2-coverage-grid/result.json'

class _Kernel:
 def __init__(self,*,m,risk_stratum,planned_discordant_p,order_offset=0,fresh_items=True):
  if type(m) is not int or m not in CONFIG['coverage_candidates']:raise ValueError('registered_m_required')
  if risk_stratum not in STRATA:raise ValueError('registered_risk_stratum_required')
  if type(order_offset) is not int or not 0<=order_offset<9:raise ValueError('registered_balanced_offset_required')
  if fresh_items is not True:raise ValueError('reuse_not_authorized')
  if type(planned_discordant_p) not in (int,float) or not math.isfinite(planned_discordant_p) or not 0<=planned_discordant_p<=1:raise ValueError('registered_effect_required')
  self.m=m;self.risk_stratum=risk_stratum;self.planned_p=planned_discordant_p;self.offset=order_offset
  self.net={s:0 for s in STRATA};self.discordance={s:0 for s in STRATA};self.counts={s:0 for s in STRATA}
  self.items=0;self.main_items=0;self.risk_items=0;self.risk_net=0;self.log_e=0.;self.seen=set()
  self.phase='primary';self.verdict='running';self.reason='collecting_primary';self.primary_accepted=False
  self.coverage_complete=False;self.regressed_strata=[]
  if planned_discordant_p<.85:self._stop('insufficient_power','registered_effect_below_mde')
 def _stop(self,verdict,reason):self.phase='done';self.verdict=verdict;self.reason=reason
 def next_stratum(self):
  if self.phase=='done':return None
  if self.phase=='risk':return self.risk_stratum
  if self.phase=='coverage':
   uncovered=[s for s in ANSWER if not(self.discordance[s]>=self.m or (self.discordance[s]==0 and self.counts[s]>=60))]
   return min(uncovered,key=lambda s:(self.counts[s],(ANSWER.index(s)-self.offset%6)%6))
  return STRATA[(self.offset+self.main_items)%9]
 def _risk_start(self):
  self.coverage_complete=all(self.discordance[s]>=self.m or (self.discordance[s]==0 and self.counts[s]>=60) for s in ANSWER)
  self.regressed_strata=[s for s in ANSWER if self.net[s]<0] if self.coverage_complete else []
  self.phase='risk';self.verdict='candidate_requires_review';self.reason='registered_risk_follow_up'
 def update(self,*,item_id,stratum,candidate,incumbent,abstain,domain_violation=False):
  if self.phase=='done':raise ValueError('terminal_process')
  if not isinstance(item_id,str) or not item_id or item_id in self.seen:raise ValueError('fresh_unique_item_required')
  if stratum!=self.next_stratum():raise ValueError('registered_schedule_required')
  if any(type(v) is not bool for v in (candidate,incumbent,abstain,domain_violation)):raise ValueError('boolean_scores_required')
  # Baseline truth must match the pre-registered nine-stratum task contract.
  if abstain!=(stratum in SAFETY):raise ValueError('abstain_truth_contract_mismatch')
  self.seen.add(item_id);self.items+=1;delta=int(candidate)-int(incumbent)
  if domain_violation:self._stop('reject_domain','observed_domain_violation');return self.verdict
  if abstain and not candidate:self._stop('reject_safety','G1_zero_tolerance');return self.verdict
  if self.phase=='risk':
   self.risk_items+=1;self.risk_net+=delta
   if self.risk_items==40:
    if self.risk_net<0:self._stop('reject_regression','risk_follow_up_net_loss')
    elif self.regressed_strata:self._stop('reject_regression','G2_net_loss')
    elif not self.coverage_complete:self._stop('insufficient_power','answer_stratum_coverage_cap')
    else:self._stop('promote_proposal','pooled_acceptance_coverage_G1_G2_risk_pass')
   return self.verdict
  self.main_items+=1;self.counts[stratum]+=1;self.net[stratum]+=delta;self.discordance[stratum]+=int(delta!=0)
  if self.phase=='primary':
   self.log_e+=math.log1p(.3*delta)
   if self.log_e<=math.log(.05):self._stop('insufficient_power','registered_futility')
   elif self.log_e>=math.log(20) and sum(self.net.values())>=3 and all(self.counts.values()):
    self.primary_accepted=True;self.phase='coverage';self.verdict='candidate_requires_review';self.reason='answer_stratum_coverage'
   elif self.main_items>=300:self._stop('insufficient_power','primary_cap_without_acceptance')
  if self.phase=='coverage' and (all(self.discordance[s]>=self.m or (self.discordance[s]==0 and self.counts[s]>=60) for s in ANSWER) or self.main_items>=960):self._risk_start()
  return self.verdict
 def report(self):
  return {'gate_id':GATE_ID,'version':VERSION,'m':self.m,'risk_stratum':self.risk_stratum,'phase':self.phase,'verdict':self.verdict,'reason':self.reason,
   'items':self.items,'main_items':self.main_items,'risk_items':self.risk_items,'log_e':self.log_e,'primary_accepted':self.primary_accepted,
   'coverage_complete':self.coverage_complete,'net':dict(self.net),'discordance':dict(self.discordance),'regressed_strata':list(self.regressed_strata),
   'planned_discordant_p':self.planned_p,'power_citation':POWER_EVIDENCE,'promotion_authorized':False,'installed':False}

def promotion_authority(gate_version,*,signature_verified=False,active_version=None):
 return signature_verified is True and active_version==VERSION and gate_version==VERSION


class Process(_Kernel):
 """Public admission requires a prospectively registered discordance scope.

 The caller must verify the bound dev-evidence hash against the study registration.
 This pure kernel checks format, threshold and claimed profile, not filesystem trust.
 """
 def __init__(self,*,declared_primary_discordance,scope_profile,scope_evidence_sha256,**kwargs):
  if type(declared_primary_discordance) not in (float,int) or not math.isfinite(declared_primary_discordance) or not 0<=declared_primary_discordance<=1:raise ValueError('registered_discordance_required')
  if not isinstance(scope_evidence_sha256,str) or len(scope_evidence_sha256)!=64 or any(c not in '0123456789abcdef' for c in scope_evidence_sha256):raise ValueError('registered_dev_scope_evidence_hash_required')
  if scope_profile not in ('broad_75','narrow_64','measured','narrow_88','other'):raise ValueError('registered_scope_profile_required')
  super().__init__(**kwargs)
  self.declared_primary_discordance=declared_primary_discordance;self.scope_profile=scope_profile;self.scope_evidence_sha256=scope_evidence_sha256
  if declared_primary_discordance<.08 or scope_profile not in ('broad_75','narrow_64','measured'):
   self._stop('insufficient_power','outside_registered_discordance_scope')
 def report(self):
  r=super().report();r.update(declared_primary_discordance=self.declared_primary_discordance,scope_profile=self.scope_profile,scope_evidence_sha256=self.scope_evidence_sha256)
  return r
