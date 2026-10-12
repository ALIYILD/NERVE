"""Scripted offline proposer, fed only observed training transitions."""
from .contracts import Rule, digest, canonical


def reflect(episodes, existing_rules=()):
    if any(e['split'] != 'train' for e in episodes):
        raise PermissionError('proposer accepts training only')
    rules, reasons, missing = {}, [], []
    for episode in episodes:
        for row in episode['transitions']:
            if row['status'] != 'observed' or row['outcome'] is None:
                missing.append(row['id'])
                continue
            key = digest([row['previous'],row['action']])
            if key in rules:
                rule = rules[key]
                if canonical(rule.predicted_effect) != canonical(row['outcome']) or rule.completion != row['completion']:
                    return {'decision':'retain','failure_class':'hidden_state_or_environment_drift',
                            'evidence':[rule.supporting_transition_ids[0],row['id']], 'rules':[]}
                rule.supporting_transition_ids.append(row['id'])
                continue
            contradiction = row['prediction'] is not None and canonical(row['prediction']) != canonical(row['outcome'])
            rules[key] = Rule('r_'+key[:24],1,episode['family'],row['previous'],row['action'],
                row['outcome'],row['completion'],[row['id']],[row['id']] if contradiction else [],status='supported')
            if contradiction:
                reasons.append(row['id'])
    if missing:
        return {'decision':'retain','failure_class':'missing_evidence','evidence':missing,'rules':[]}
    proposed = [r.to_dict() for _,r in sorted(rules.items())]
    if not proposed:
        return {'decision':'retain','failure_class':'no_new_evidence','evidence':[],'rules':[]}
    old_program = [(r['preconditions'],r['action'],r['predicted_effect'],r['completion']) for r in existing_rules]
    new_program = [(r['preconditions'],r['action'],r['predicted_effect'],r['completion']) for r in proposed]
    return {'decision':'repair_code' if old_program == new_program else 'revise_rulebook',
            'failure_class':'execution_error' if old_program == new_program else 'rule_mismatch',
            'evidence':reasons or [r['supporting_transition_ids'][0] for r in proposed], 'rules':proposed,
            'provider':'scripted offline proposer'}
