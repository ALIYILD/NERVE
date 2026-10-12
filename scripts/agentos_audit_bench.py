"""Offline development checks for typed audit evidence. Makes no model calls."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from nerve_awim import agentos_audit_evidence as oracle
from nerve_awim.agentos_audit_fixtures import development_cases

SCHEMA = 'nerve-audit-development-manifest-v1'
LIMITATION = ('Public simulated development controls, not sealed holdouts, live audits, '
              'model performance, or learned-policy improvement evidence.')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def preflight():
    cases = development_cases()
    ids = [case['id'] for case in cases]
    if not cases or len(ids) != len(set(ids)):
        raise ValueError('unique nonempty development cases required')
    results = []
    for case in cases:
        oracle.validate_bundle(case['bundle'])
        expected = oracle.expected_decision(case['bundle'])
        correct = oracle.judge_decision(case['bundle'], case['expected'])['passed']
        if expected != case['expected'] or not correct:
            raise ValueError('hand-authored gold disagrees with oracle: ' + case['id'])
        results.append({'id': case['id'], 'family': case['family'], 'passed': True})
    unknown = {'decision': 'unknown', 'citations': []}
    supported = {'decision': 'supported', 'citations': []}
    unknown_hits = sum(oracle.judge_decision(c['bundle'], unknown)['passed'] for c in cases)
    supported_hits = sum(oracle.judge_decision(c['bundle'], supported)['passed'] for c in cases)
    if unknown_hits == len(cases) or supported_hits == len(cases):
        raise ValueError('constant response defeats development controls')
    return {'passed': len(results), 'total': len(results), 'checks': results,
            'constant_unknown_hits': unknown_hits, 'uncited_supported_hits': supported_hits,
            'development_only': True, 'native_sessions': 0,
            'promotion_authorized': False, 'limitation': LIMITATION}


def build_manifest():
    checks = preflight()
    body = {'schema': SCHEMA, 'oracle_revision': oracle.evaluator_revision(),
            'runner_revision': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'cases': development_cases(), 'preflight': checks,
            'development_only': True, 'promotion_authorized': False}
    return {**body, 'manifest_sha256': digest(body)}


def validate_manifest(value):
    if type(value) is not dict or set(value) != {
            'schema', 'oracle_revision', 'runner_revision', 'cases', 'preflight', 'development_only',
            'promotion_authorized', 'manifest_sha256'}:
        raise ValueError('invalid development manifest schema')
    body = {k: v for k, v in value.items() if k != 'manifest_sha256'}
    if (value['schema'] != SCHEMA or value['development_only'] is not True
            or value['promotion_authorized'] is not False
            or digest(body) != value['manifest_sha256']):
        raise ValueError('manifest integrity or scope mismatch')
    if (value['oracle_revision'] != oracle.evaluator_revision()
            or value['runner_revision'] != hashlib.sha256(Path(__file__).read_bytes()).hexdigest()):
        raise ValueError('oracle revision changed; do not compare against this manifest')
    # A hash alone is not authority: accept only this reviewed development fixture.
    if digest(value['cases']) != digest(development_cases()) or digest(value['preflight']) != digest(preflight()):
        raise ValueError('manifest differs from reviewed development controls')
    return value


def grade(manifest, answers):
    manifest = validate_manifest(manifest)
    cases = manifest['cases']
    valid_batch = type(answers) is dict and set(answers) == {c['id'] for c in cases}
    rows = []
    for case in cases:
        output = answers.get(case['id']) if type(answers) is dict else None
        check = oracle.judge_decision(case['bundle'], output)
        passed = valid_batch and check['passed']
        rows.append({'id': case['id'], 'passed': bool(passed),
                     'category': check['category'] if valid_batch else 'invalid_batch',
                     'expected_decision': case['expected']['decision'],
                     'observed_decision': output.get('decision') if type(output) is dict else None})
    unsupported = sum(r['observed_decision'] == 'supported' and r['expected_decision'] != 'supported' for r in rows)
    positive = [r for r in rows if r['expected_decision'] == 'supported']
    unknown = [r for r in rows if r['expected_decision'] == 'unknown']
    return {'manifest_sha256': manifest['manifest_sha256'], 'answers_sha256': digest(answers),
            'valid_batch': valid_batch, 'passed': sum(r['passed'] for r in rows), 'total': len(rows),
            'checks': rows, 'unsupported_positive_count': unsupported,
            'supported_claims_correct': sum(r['passed'] for r in positive), 'supported_claims_total': len(positive),
            'unknown_claims_correct': sum(r['passed'] for r in unknown), 'unknown_claims_total': len(unknown),
            'development_only': True, 'promotion_authorized': False, 'limitation': LIMITATION}


def read_json(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(1000001)
    if len(raw) > 1000000:
        raise ValueError('input exceeds one megabyte')
    def reject_constant(value):
        raise ValueError('non-finite JSON number')
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, parse_constant=reject_constant, object_pairs_hook=unique_object)


def save_new(path, value):
    data = json.dumps(value, indent=2, allow_nan=False) + '\n'
    # Exclusive creation preserves existing manifests and receipts, including partial writes.
    with Path(path).open('x') as stream:
        stream.write(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('preflight')
    freeze = sub.add_parser('freeze')
    freeze.add_argument('--output', type=Path, required=True)
    tasks = sub.add_parser('tasks')
    tasks.add_argument('--manifest', type=Path, required=True)
    evaluate = sub.add_parser('grade')
    evaluate.add_argument('--manifest', type=Path, required=True)
    evaluate.add_argument('--answers', type=Path, required=True)
    evaluate.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'preflight':
        result = preflight()
    elif args.command == 'freeze':
        manifest = build_manifest()
        save_new(args.output, manifest)
        result = {'manifest': str(args.output), 'manifest_sha256': manifest['manifest_sha256']}
    elif args.command == 'tasks':
        manifest = validate_manifest(read_json(args.manifest))
        result = {'development_only': True, 'tasks': [{'id': c['id'], 'bundle': c['bundle']} for c in manifest['cases']]}
    else:
        result = grade(read_json(args.manifest), read_json(args.answers))
        save_new(args.output, result)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
