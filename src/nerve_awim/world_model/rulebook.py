"""Readable rendering of canonical rules; imported text never confers authority."""
from .contracts import Rule


def render(rules):
    lines = ['# Operational rulebook', '', 'Uncalibrated synthetic hypotheses; no activation authority.', '']
    for raw in rules:
        r = Rule.load(raw)
        lines.extend([f'## {r.rule_id} (v{r.version}, {r.status})', '',
                      f'Action: `{r.action}`', f'Preconditions: `{r.preconditions}`',
                      f'Predicted effect: `{r.predicted_effect}`',
                      'Evidence: '+', '.join(r.supporting_transition_ids), ''])
    return '\n'.join(lines)
