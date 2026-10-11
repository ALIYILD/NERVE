"""Bounded offline selection of data-only prompt/tool recipes; no execution."""
from copy import deepcopy
from .learning_study import canonical


def select_recipe(recipes, tasks, *, evaluate, max_calls=100):
    """Trusted evaluator returns a boolean for each recipe/task pair.

    Selection data only, never final holdout. Results are proposals for separate
    evaluation, not release approvals. No source code, permissions or tools are
    introduced by recipe strings. The host must keep evaluate read-only/bounded.
    """
    recipes, tasks = deepcopy(tuple(recipes)), deepcopy(tuple(tasks))
    if not 2 <= len(recipes) <= 16 or not 3 <= len(tasks) <= 100:
        raise ValueError('bounded recipes and selection tasks required')
    if type(max_calls) is not int or not 1 <= max_calls <= 1000 or len(recipes)*len(tasks) > max_calls:
        raise ValueError('evaluation budget exceeded')
    keys = []
    for recipe in recipes:
        if type(recipe) is not dict or set(recipe) != {'prompt', 'strategy'}:
            raise ValueError('exact data-only recipe schema required')
        if any(type(recipe[k]) is not str or not 1 <= len(recipe[k]) <= 2048 for k in recipe):
            raise ValueError('bounded recipe strings required')
        keys.append(canonical(recipe))
    if len(set(keys)) != len(keys):
        raise ValueError('distinct recipes required')
    for task in tasks:
        canonical(task)
    scores = []
    for recipe in recipes:
        hits = 0
        for task in tasks:
            success = evaluate(deepcopy(recipe), deepcopy(task))
            if type(success) is not bool:
                raise ValueError('independent boolean evaluation required')
            hits += int(success)
        scores.append(hits)
    # First recipe is the incumbent; ties retain it.
    selected = max(range(len(recipes)), key=lambda index: (scores[index], -index))
    return {'recipe': deepcopy(recipes[selected]), 'hits': scores, 'tasks': len(tasks),
            'calls': len(recipes)*len(tasks), 'improved_on_selection': scores[selected] > scores[0],
            'requires_fresh_evaluation': True, 'promotion_authorized': False}
