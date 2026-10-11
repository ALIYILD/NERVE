"""Network-free multi-family fixture. Controlled faults are not learned skills."""
import ast
import csv
import io
import json
from nerve_awim.learning_study import Episode
from nerve_awim.improvement_loop import run_improvement_loop


def partitions():
    def make(phase, name, rows):
        return tuple(Episode(name+str(n), phase, task, expected) for n, (task, expected) in enumerate(rows))
    train = make('train', 'train-', [
        ({'family':'sort', 'values':[3,1,2]}, [1,2,3]),
        ({'family':'unique', 'values':['b','a','b']}, ['b','a']),
        ({'family':'json', 'text':'{"item":4}', 'key':'item'}, 4),
        ({'family':'python', 'source':'def train_fn():\n    pass\n'}, ['train_fn']),
    ])
    selection = make('evaluation', 'select-', [
        ({'family':'sort', 'values':[7,-2,4]}, [-2,4,7]),
        ({'family':'sort', 'values':[5,5,0]}, [0,5,5]),
        ({'family':'unique', 'values':['x','y','x','z']}, ['x','y','z']),
        ({'family':'unique', 'values':[2,1,2,1]}, [2,1]),
        ({'family':'json', 'text':'{"item":[1,3]}', 'key':'item'}, [1,3]),
        ({'family':'json', 'text':'{"item":false}', 'key':'item'}, False),
        ({'family':'python', 'source':'class C:\n    def method(self): pass\ndef select_fn(): pass\n'}, ['select_fn']),
        ({'family':'python', 'source':'async def async_fn(): pass\n'}, ['async_fn']),
    ])
    regression = make('evaluation', 'retain-', [
        ({'family':'unique', 'values':['r','s','r']}, ['r','s']),
        ({'family':'unique', 'values':[9,8,9]}, [9,8]),
        ({'family':'sort', 'values':[-8,2,0]}, [-8,0,2]),
        ({'family':'json', 'text':'{"keep":null}', 'key':'keep'}, None),
        ({'family':'python', 'source':'def retained():\n    def inner(): pass\n'}, ['retained']),
    ])
    final = make('evaluation', 'final-', [
        ({'family':'sort', 'values':[-9,6,-4,6]}, [-9,-4,6,6]),
        ({'family':'unique', 'values':['f','g','f','h','g']}, ['f','g','h']),
        ({'family':'json', 'text':'{"final":{"ok":true}}', 'key':'final'}, {'ok':True}),
        ({'family':'python', 'source':'if True:\n    def conditional(): pass\n@decorator\ndef final_fn(): pass\n'}, ['final_fn']),
        # CSV is unseen in train/selection/regression. It is not a newly learned
        # capability: the capable predictor already implements the CSV parser.
        ({'family':'csv', 'text':'a,"b,c"\n'}, [['a','b,c']]),
        ({'family':'csv', 'text':'"x""y",z\n'}, [['x"y','z']]),
    ])
    return train, selection, regression, final


def capable(task, lesson=None):
    family = task['family']
    if family == 'sort':
        return sorted(task['values'])
    if family == 'unique':
        return list(dict.fromkeys(task['values']))
    if family == 'json':
        return json.loads(task['text'])[task['key']]
    if family == 'python':
        return [n.name for n in ast.parse(task['source']).body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if family == 'csv':
        return list(csv.reader(io.StringIO(task['text'])))
    raise ValueError('unsupported fixture family')


def run():
    train, selection, regression, final = partitions()
    def faulty(task, lesson):
        # Explicitly injected baseline fault and regression, not an AI learner.
        if lesson is None and task['family'] == 'sort':
            return list(reversed(sorted(task['values'])))
        if lesson == 'repair-with-forgetting' and task['family'] == 'python' and 'retained' in task['source']:
            return []
        return capable(task)
    results = {}
    for name, predict, proposals in (
        ('capable_control', capable, ('advisory-only',)),
        ('controlled_repair', faulty, ('repair-with-forgetting', 'repair-without-forgetting')),
    ):
        results[name] = run_improvement_loop(train, selection, final, regression=regression,
            propose=lambda request: proposals[min(request['iteration']-1, len(proposals)-1)],
            predict=predict, judge=lambda task, output, expected: type(output) is type(expected) and output == expected)
    final_families = {}
    for item in final:
        family = item.task['family']
        row = final_families.setdefault(family, {'hits':0, 'tasks':0})
        row['tasks'] += 1
        row['hits'] += int(capable(item.task) == item.expected)
    return {'scope':'offline deterministic fixture; no model learning or generalization claim',
            'api_calls':0, 'cost_usd':0, 'families':5, 'capable_final_by_family':final_families,
            'scenarios':results, 'promotion_authorized':False}


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
