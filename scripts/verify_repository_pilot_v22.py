"""Exercise a sealed real-repository pilot through five fresh CLI processes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def verify():
    with tempfile.TemporaryDirectory() as folder:
        def run(action, extra=()):
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/repository_pilot_v22.py'),
                action, '--db', str(Path(folder) / 'pilot.db'), '--study', 'ci-pilot',
                '--root', str(ROOT), *extra], cwd=ROOT,
                env={**os.environ, 'PYTHONPATH': str(ROOT / 'src')},
                capture_output=True, text=True, check=True, timeout=30)
            return json.loads(result.stdout)
        planned = run('plan', ('--manifest', str(ROOT / 'benchmarks/repository_pilot_manifest_v22.json')))
        collected = run('collect')
        frozen = run('freeze')
        evaluated = run('evaluate')
        reviewed = run('review')
        assert collected['collection']['recorded'] == 3
        assert frozen['candidate'] == reviewed['review']['candidate']
        assert evaluated['evaluation']['status'] == 'rejected'
        assert reviewed['review']['recommendation'] == 'reject_rollout'
        assert reviewed['review']['manifest_sha256'] == planned['review']['manifest_sha256']
        assert reviewed['review']['active_release'] == planned['review']['active_release']
        assert reviewed['review']['generation'] == 0
        return {'status': 'sealed_pilot_verified', 'fresh_processes': 5,
                'source': 'actual NERVE files; repeated CI fixtures are not fresh external evidence',
                'review': reviewed['review']}


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2, sort_keys=True))
