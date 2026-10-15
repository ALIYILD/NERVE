"""Verify identical pinned goal code and subprocess restart in both hosts."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def verify(root, domain, *, auto_adapt=False):
    vendor = root / 'scripts/nerve_goal_core'
    manifest = json.loads((vendor / 'PROVENANCE.json').read_text())
    for filename, expected_hash in manifest['sha256'].items():
        upstream = ROOT / ('src/nerve_awim' if filename.endswith('.py') else '') / filename
        content = (vendor / filename).read_bytes()
        if content != upstream.read_bytes() or sha256(content).hexdigest() != expected_hash:
            raise ValueError('vendor source drift: ' + filename)
    with tempfile.TemporaryDirectory(prefix='nerve-host-goal-') as directory:
        def command(action):
            script = 'nerve_auto_adapt.py' if auto_adapt else 'nerve_goal.py'
            result = subprocess.run([sys.executable, str(root / 'scripts' / script),
                                     action, '--state', directory], check=True,
                                    capture_output=True, text=True, timeout=30)
            return json.loads(result.stdout)
        for _ in range(9 if auto_adapt else 2):
            adopted = command('tick')
        if adopted['status'] != 'active':
            raise AssertionError('goal completed before monitoring')
        completed = command('run')
        if completed['status'] != 'complete' or command('run') != completed:
            raise AssertionError('restart changed state or repeated execution')
        if auto_adapt:
            result = completed['tasks'][-1]['receipt']['domains'][domain+':verify-recovery']
            if not result['beats_all_fixed_controls'] or not result['rollback_probe']['rollback_verified']:
                raise AssertionError('adaptation or rollback target failed')
            return dict(result, subprocess_restart_verified=True, source_verified=True,
                        source_commit=manifest['upstream_commit'], protocol='auto-adapt-aba-v1')
        study = next(t['receipt'] for t in completed['tasks'] if t['id'] == domain+':study')
        monitor = next(t['receipt'] for t in completed['tasks'] if t['id'] == domain+':monitor')
        if study['final']['losses'] or not monitor['rollback_verified']:
            raise AssertionError('regression or rollback failure')
        return {'domain': domain, 'status': completed['status'], 'subprocess_restart_verified': True,
                'source_verified': True, 'source_commit': manifest['upstream_commit'],
                'final': study['final'], 'capable_control_hits': study['capable_control_hits'],
                'monitor': monitor, 'production_authorized': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clinical-root', type=Path, required=True)
    parser.add_argument('--perfflux-root', type=Path, required=True)
    parser.add_argument('--auto-adapt', action='store_true')
    args = parser.parse_args()
    print(json.dumps([verify(args.clinical_root, 'clinical_os', auto_adapt=args.auto_adapt),
                      verify(args.perfflux_root, 'perfflux', auto_adapt=args.auto_adapt)], indent=2))
