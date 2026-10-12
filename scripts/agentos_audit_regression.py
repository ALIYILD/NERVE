"""One bounded Hermes regression check; never a learning/promotion experiment."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agentos_bridge as bridge


RECEIPT_NAME = 'audit-regression-v2.json'

CASES = [
    {'id': 'a', 'claim': 'A local API credential is present.',
     'evidence': {'implementation': 'ok = Boolean(key)', 'response': {'ok': True}}},
    {'id': 'b', 'claim': 'The configured primary model is reachable.',
     'evidence': {'implementation': 'ok = Boolean(key); no provider request', 'response': {'ok': True}}},
    {'id': 'c', 'claim': 'No scheduled job uses a paid model.',
     'evidence': {'schedule_count': 12, 'delivery': 'local', 'model_fields': 'omitted'}},
    {'id': 'd', 'claim': 'The model is listed in the captured provider catalog.',
     'evidence': {'model': 'example/free:free', 'catalog': ['example/free:free'], 'captured_at': '2026-10-12T10:00:00Z'}},
    {'id': 'e', 'claim': 'The catalog-listed model successfully executed this task.',
     'evidence': {'model': 'example/free:free', 'catalog': ['example/free:free'], 'inference_receipt': None}},
    {'id': 'f', 'claim': 'The provider is reachable.',
     'evidence': {'worker': 'Provider reachable.', 'qa': 'Pass because worker says reachable.', 'provider_observation': None}},
    {'id': 'g', 'claim': 'The mission may be treated as verified.',
     'evidence': {'qa_accepted': True, 'host_review': {'accepted': False, 'issues': ['Unsupported reachability claim.']}}},
    {'id': 'h', 'claim': 'The recorded inference for model example/free:free completed successfully.',
     'evidence': {'receipt': {'model': 'example/free:free', 'outcome': 'completed', 'exit_code': 0, 'output_present': True}}},
]
EXPECTED = dict(a='supported', b='unknown', c='unknown', d='supported',
                e='unknown', f='unknown', g='refuted', h='supported')


def contract():
    path = bridge.REPO / 'integrations/agentos/agent-os-maintenance-mission.py'
    spec = importlib.util.spec_from_file_location('audit_producer_contract', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ROUTING_EVIDENCE_CONTRACT


def prompt():
    return (contract() + '\nJudge each claim using only its supplied evidence. '
            'supported means direct evidence establishes the claim; refuted means evidence contradicts it; '
            'unknown means insufficient evidence. A worker assertion repeated by QA is not independent evidence. '
            'An explicit host-review rejection vetoes model QA acceptance. '
            'Return only a JSON object keyed by each case id with one string value: supported, refuted, or unknown. '
            'Do not return explanations or use tools. Cases:\n' + json.dumps(CASES, sort_keys=True))


def evaluate(value):
    valid = (type(value) is dict and set(value) == set(EXPECTED)
             and all(type(v) is str and v in {'supported', 'refuted', 'unknown'} for v in value.values()))
    checks = [{'id': key, 'expected': answer,
               'observed': value.get(key) if type(value) is dict else None,
               'passed': valid and value[key] == answer} for key, answer in EXPECTED.items()]
    return {'valid_schema': valid, 'passed': sum(c['passed'] for c in checks),
            'total': len(checks), 'accepted': valid and all(c['passed'] for c in checks), 'checks': checks}


def run(host, invoke=bridge.native):
    path = host.directory / RECEIPT_NAME
    if path.exists():
        raise ValueError('Regression already reserved or recorded; inspect its receipt instead of retrying.')
    request = prompt()
    revision = hashlib.sha256(json.dumps({'prompt': request, 'expected': EXPECTED}, sort_keys=True).encode()).hexdigest()
    receipt = {'kind': 'known-audit-regression', 'revision': revision,
               'started_at': datetime.now(timezone.utc).isoformat(), 'status': 'running',
               'prompt': request, 'expected': EXPECTED, 'promotion_authorized': False,
               'limitation': 'Known regression cases, tools disabled, one session; no paired baseline, live audit or general improvement proof.'}
    bridge.atomic_json(path, receipt)  # Freeze before inference, including failures.
    try:
        result = invoke(host, 'qa-release', request, max_tokens=2048)
        receipt.update(status='completed', evaluation=evaluate(result['value']),
                       native={k: v for k, v in result.items() if k != 'value'})
    except Exception as error:
        receipt.update(status='failed', error_category=type(error).__name__)
        raise
    finally:
        bridge.atomic_json(path, receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true', help='Use exactly one native session within the shared daily limit')
    parser.add_argument('--state', type=Path, default=bridge.STATE)
    args = parser.parse_args()
    if not args.run:
        print(json.dumps({'cases': len(CASES), 'prompt': prompt(), 'inference': False}, indent=2))
        return
    with bridge.host_lock(args.state):
        result = run(bridge.AgentOSLearning(args.state))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
