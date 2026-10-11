"""Offline chronological study with frozen evaluation and isolated arm state.

Trusted callbacks only; no sandbox, remote model calls, or deployment authority.
"""
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from time import perf_counter


@dataclass(frozen=True)
class Episode:
    episode_id: str
    phase: str
    task: dict
    expected: object


def canonical(value):
    encoded = json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':'))
    if len(encoded.encode()) > 16384:
        raise ValueError('bounded JSON value required')
    return encoded


def validate_stream(episodes):
    episodes = tuple(deepcopy(episodes))
    if not 8 <= len(episodes) <= 1000:
        raise ValueError('8 to 1000 episodes required')
    ids, payloads, evaluation = set(), set(), False
    counts = {'train': 0, 'evaluation': 0}
    for item in episodes:
        if type(item) is not Episode or item.phase not in counts:
            raise ValueError('typed train/evaluation episodes required')
        if type(item.episode_id) is not str or not 1 <= len(item.episode_id) <= 96:
            raise ValueError('bounded episode ID required')
        if type(item.task) is not dict:
            raise ValueError('JSON object task required')
        digest = sha256(canonical(item.task).encode()).hexdigest()
        canonical(item.expected)
        if item.episode_id in ids or digest in payloads:
            raise ValueError('duplicate ID or exact task across study splits')
        if evaluation and item.phase == 'train':
            raise ValueError('training cannot follow evaluation')
        evaluation |= item.phase == 'evaluation'
        ids.add(item.episode_id)
        payloads.add(digest)
        counts[item.phase] += 1
    if counts['train'] < 3 or counts['evaluation'] < 5:
        raise ValueError('at least three training and five evaluation episodes required')
    return episodes


def run_study(episodes, *, arm_factory, judge):
    """Arms expose predict(task) and learn(task, output, success, episode_id).

    Factories must construct independent trusted arms. The predictor never
    receives expected answers. Evaluation results never reach learn().
    Callback exceptions fail the study; partial reports cannot imply success.
    """
    stream = validate_stream(episodes)
    results, instances = {}, []
    for name in ('no_memory', 'lexical', 'adaptive'):
        arm = arm_factory(name)
        if any(arm is previous for previous in instances):
            raise ValueError('each arm needs independent state')
        instances.append(arm)
        hits = count = trained = 0
        elapsed = 0.
        outcomes = []
        for item in stream:
            start = perf_counter()
            output = arm.predict(deepcopy(item.task))
            canonical(output)
            duration = (perf_counter()-start)*1000
            accepted = judge(deepcopy(item.task), deepcopy(output), deepcopy(item.expected))
            if type(accepted) is not bool:
                raise ValueError('independent judge must return boolean')
            if item.phase == 'train':
                arm.learn(deepcopy(item.task), deepcopy(output), accepted, item.episode_id)
                trained += 1
            else:
                hits += int(accepted)
                count += 1
                elapsed += duration
                outcomes.append(accepted)
        results[name] = {'hits': hits, 'tasks': count, 'accuracy': hits/count,
                         'training_episodes': trained, 'mean_prediction_ms': elapsed/count,
                         'outcomes': outcomes, 'cost_usd': None}
    paired = {}
    adaptive = results['adaptive']['outcomes']
    for name in ('no_memory', 'lexical'):
        control = results[name]['outcomes']
        paired[name] = {'wins': sum(a and not b for a,b in zip(adaptive, control)),
                        'losses': sum(b and not a for a,b in zip(adaptive, control))}
    return {'arms': results, 'paired_adaptive': paired, 'evaluation_feedback_written': False,
            'promotion_authorized': False,
            'scope': 'offline host-controlled study; no generalization claim'}
