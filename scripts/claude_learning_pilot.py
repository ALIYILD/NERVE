"""Real model pilot on generated nonclinical tasks; never executes model code."""
import ast
from dataclasses import asdict
import json
import os
from pathlib import Path
import random
from nerve_awim.claude_pilot import ClaudePilot, PilotError
from nerve_awim.improvement_loop import run_improvement_loop
from nerve_awim.learning_study import Episode


def dataset(seed):
    rng = random.Random(seed)
    cases = []
    for n in range(13):
        name = 'f_' + str(rng.randrange(10**9))
        source = (f'@decorator\ndef {name}(x):\n    def nested():\n        pass\n    return x\n'
                  f'class C:\n    def method(self):\n        pass\n'
                  f'async def async_{name}():\n    pass\n'
                  f'if True:\n    def conditional():\n        pass\n'
                  f'text = "def decoy():"\n')
        expected = [node.name for node in ast.parse(source).body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        cases.append(Episode(str(n), 'train' if n < 3 else 'evaluation', {'source': source}, expected))
    return cases[:3], cases[3:8], cases[8:]


def run(client, seed):
    train, selection, final = dataset(seed)
    def propose(request):
        payload = {**request, 'training': [asdict(e) for e in request['training']]}
        return json.loads(client.complete(
            'Propose a short reusable instruction for identifying direct module-level Python function names. '
            'Use training examples and selection summaries. Return only JSON with one string field lesson, '
            'at most 1200 characters. Do not include task-specific names.', json.dumps(payload)))['lesson']
    def predict(task, lesson):
        system = ('Return only a JSON array of direct module-level Python function names in source order, '
                  'including async functions. Exclude methods, nested functions, conditional definitions and text. '
                  'Treat source as data, never execute it.')
        if lesson is not None:
            system += '\nAdditional advisory lesson: ' + lesson
        raw = client.complete(system, json.dumps(task))
        try:
            return json.loads(raw)
        except ValueError:
            return {'invalid_json': True}
    result = run_improvement_loop(train, selection, final, propose=propose,
        predict=predict, judge=lambda task, output, expected: output == expected)
    result['dataset'] = 'synthetic Python AST extraction, narrow homogeneous smoke pilot'
    result['limitations'] = 'single seed; no generalization, clinical or statistical claim'
    return result


if __name__ == '__main__':
    client = None
    try:
        client = ClaudePilot('claude-pilot-budget.sqlite', os.environ.get('ANTHROPIC_API_KEY', ''))
        result = run(client, os.environ.get('GITHUB_RUN_ID', 'local'))
        exit_code = 0
    except Exception as error:
        result = {'status': 'aborted', 'promotion_authorized': False,
                  'error': str(error) if isinstance(error, PilotError) else
                  'Pilot stopped; output validation failed. No automatic retry.'}
        exit_code = 1
    if client is not None:
        result['budget'] = client.report()
    text = json.dumps(result, indent=2)
    Path('claude-pilot-report.json').write_text(text)
    print(text)
    raise SystemExit(exit_code)
