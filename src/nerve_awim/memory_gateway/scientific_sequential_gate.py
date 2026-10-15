"""Non-canonical simulation-only paired anytime-valid gate, Loop 40.2 v2.

Registered b in (0,1): E *= 1+b for a discordant win, 1-b for a
loss, 1 for a tie. Under conditional P(win | discordant,past)<=1/2,
E is a nonnegative supermartingale; Ville bounds a threshold crossing by alpha.
Reverse per-stratum processes test for harm vs always-abstain. A non-crossing
veto is NOT proof of stratum noninferiority. Nothing here installs a candidate.
"""
import math
from .scientific_sequential_journal import Journal

VERSION = 'scientific-sequential-gate-v2-simulation'


class Process:
    def __init__(self, gate):
        self.g = gate
        self.log_e = 0.; self.net = 0; self.items = 0
        self.reverse = {s:0. for s in gate['strata']}
        self.counts = {s:0 for s in gate['strata']}
        self.veto = False; self.verdict = 'running'; self.reason = 'collecting'

    def update(self, *, candidate, incumbent, abstain, stratum, violations=False):
        if self.verdict != 'running': raise ValueError('terminal_process')
        if any(type(x) is not bool for x in (candidate, incumbent, abstain)):
            raise ValueError('boolean_scores_required')
        if stratum not in self.counts: raise ValueError('unregistered_stratum')
        delta = int(candidate)-int(incumbent)
        self.log_e += math.log1p(self.g['bet']*delta)
        self.net += delta; self.items += 1; self.counts[stratum] += 1
        self.reverse[stratum] += math.log1p(self.g['bet']*(int(abstain)-int(candidate)))
        self.veto |= self.reverse[stratum] >= -math.log(self.g['alpha']/len(self.reverse))
        if violations or self.veto:
            self.verdict, self.reason = 'retain_incumbent', 'domain_or_stratum_veto'
        elif self.g['futility_e'] and self.log_e <= math.log(self.g['futility_e']):
            self.verdict, self.reason = 'retain_incumbent', 'registered_futility_bound'
        elif (self.log_e >= -math.log(self.g['alpha']) and
              self.net >= self.g['minimum_net_wins'] and all(self.counts.values())):
            self.verdict, self.reason = 'promote_proposal', 'e_threshold_and_plateau'
        elif self.items >= self.g['item_budget']:
            self.verdict, self.reason = 'insufficient_power', 'item_budget'
        return self.verdict

    def report(self):
        return dict(version=VERSION, verdict=self.verdict, reason=self.reason,
                    items=self.items, log_e=self.log_e, e_value=math.exp(min(700,self.log_e)),
                    net_wins=self.net, marginal_delta=self.net/self.items if self.items else 0,
                    strata_counts=self.counts.copy(), stratum_veto=self.veto,
                    stratum_reverse_log_e=self.reverse.copy(),
                    minimum_net_wins=self.g['minimum_net_wins'],
                    promotion_authorized=False, holdout_accessed=False, model_calls=0)


class Gate(Journal):
    def __init__(self, directory, *, wallet, key, expected_ledger_head=None):
        self.wallet = wallet
        super().__init__(directory, key=key, total_alpha=wallet.verify()['total_alpha'],
                         expected_ledger_head=expected_ledger_head)

    def start(self, registration):
        self.wallet.authorize(registration)
        expected = self.wallet.path.parent / "journals" / registration["study_id"]
        if self.root.resolve() != expected.resolve():
            raise ValueError("single_authoritative_journal_path_required")
        return super().start(registration)

    def _verdict(self, registration, events):
        self.wallet.authorize(registration)
        process = Process(registration['gate'])
        rows = [e for e in events if e['kind'] == 'outcome']
        for row in rows:
            process.update(candidate=row['candidate'], incumbent=row['incumbent'],
                           abstain=row['controls']['always_abstain'], stratum=row['stratum'],
                           violations=bool(row['violations']))
        result = process.report()
        result['pending_claims'] = sum(e['kind']=='claim' for e in events)-len(rows)
        if result['pending_claims']:
            result.update(verdict='incomplete_infrastructure', reason='unresolved_claim_no_redispatch')
        return result
