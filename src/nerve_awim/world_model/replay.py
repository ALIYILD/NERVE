"""Full-episode replay with observation and completion checked separately."""
from .sandbox import execute
from .contracts import canonical


def replay(program, episodes):
    failures, compared, unknown, goals = [], 0, 0, 0
    for episode in episodes:
        rows = episode['transitions']
        if not rows:
            failures.append({'episode':episode['episode'],'reason':'empty_episode'})
            continue
        predicted = execute(program,episode['initial'],[r['action'] for r in rows])
        for row, prediction in zip(rows,predicted):
            compared += 1
            unknown += prediction['observation'] is None or prediction['goal'] is None
            if row['status'] != 'observed':
                failures.append({'episode':episode['episode'],'transition':row['id'],'reason':'missing_outcome'})
                break
            observation_ok = canonical(prediction['observation']) == canonical(row['outcome']) and prediction['observation'] is not None
            goal_ok = prediction['goal'] is row['completion'] and row['completion'] is not None
            goals += goal_ok
            if not observation_ok or not goal_ok:
                failures.append({'episode':episode['episode'],'transition':row['id'],
                                 'rule_id':prediction['rule_id'],'reason':'observation' if not observation_ok else 'completion'})
                break
    return {'replay_pass':bool(compared) and not failures, 'compared':compared,
            'goal_matches':goals,'unknown_fraction':unknown/compared if compared else 1.,'failures':failures}
