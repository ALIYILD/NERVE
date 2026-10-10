"""Cross-process shadow collection/proposal/holdout smoke check on real files."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TRAIN = ('identity_v26.py', 'recovery_v24.py', 'key_rotation_v28.py')
HOLDOUT = ('adaptive_calibration_v19.py', 'recovery_v25.py', 'drift_v14.py',
           'coverage_v18.py', 'risk_v17.py')


def verify():
    with tempfile.TemporaryDirectory() as folder:
        db = str(Path(folder) / 'shadow.db')
        def run(action, files=(), extra=()):
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/repository_shadow_v21.py'),
                action, '--db', db, '--root', str(ROOT),
                *[part for name in files for part in ('--file', 'src/nerve_awim/' + name)],
                *extra], cwd=ROOT, env={**os.environ, 'PYTHONPATH': str(ROOT / 'src')},
                capture_output=True, text=True, check=True, timeout=30)
            return json.loads(result.stdout)
        collected = run('run', TRAIN)
        restored = run('report')
        proposal = run('propose')['proposal']
        evaluated = run('evaluate', HOLDOUT, ('--candidate', proposal['candidate']))
        replay = run('run', HOLDOUT[:1])
        assert collected['collection']['recorded'] == len(TRAIN)
        assert restored['shadow']['actual_active_outcomes'][0]['tasks'] == len(TRAIN)
        assert evaluated['evaluation']['status'] == 'rejected'  # no gain over strong control
        assert replay['collection']['rejected'] == 1
        assert evaluated['status']['active_release'] == collected['status']['active_release']
        assert evaluated['status']['generation'] == 0
        return {'status': 'shadow_verified', 'training_files': len(TRAIN),
                'heldout_files': len(HOLDOUT), 'fresh_process_restore': True,
                'active_release_unchanged': True, 'holdout_replay_rejected': True,
                'evaluation': evaluated['evaluation'],
                'scope': 'same-repository integration fixtures, not fresh external validation'}


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2, sort_keys=True))
