"""Install the local free-model learning cycle; no paid reviewer is scheduled."""
from pathlib import Path
import plistlib
import sys

home = Path.home()
repo = Path(__file__).resolve().parents[1]
logs = home / 'AgentOS-Vault/Journal/nerve'
logs.mkdir(parents=True, exist_ok=True)
target = home / 'Library/LaunchAgents/com.aliyildirim.nerve.learning.plist'
target.parent.mkdir(parents=True, exist_ok=True)
payload = {
    'Label': 'com.aliyildirim.nerve.learning',
    'ProgramArguments': [sys.executable, str(repo / 'scripts/agentos_bridge.py'), 'cycle'],
    'WorkingDirectory': str(repo),
    'StartInterval': 900,
    'RunAtLoad': True,
    'EnvironmentVariables': {'PATH': '/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin'},
    'StandardOutPath': str(logs / 'cycle.log'),
    'StandardErrorPath': str(logs / 'cycle-error.log'),
}
with target.open('wb') as stream:
    plistlib.dump(payload, stream)
print(target)
