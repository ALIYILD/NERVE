#!/bin/bash
set -euo pipefail
umask 077
cd /root
printf '%s  %s\n' '6b61fdc3cd68ca4d9ed45fb937b46765936e9e049827ce3133b4278ad8f921dc' 'nerve-attended-bank-v3.private.tar.gz' | sha256sum -c -
printf '%s  %s\n' '387330b9cfd9bd6ac2d30a3d45af6867ba1e20f175aaa33e6550e6d8d374997d' 'nerve-canada-prior-state.private.tar.gz' | sha256sum -c -
test ! -e /root/nerve-attended-source
test ! -e /root/nerve-attended-bank-v3
test ! -e /root/nerve-attended-budget
mkdir -m 700 /root/nerve-attended-source
tar -xzf /root/nerve-canada-source.tar.gz -C /root/nerve-attended-source
tar -xzpf /root/nerve-attended-bank-v3.private.tar.gz -C /root
tar -xzpf /root/nerve-canada-prior-state.private.tar.gz -C /root
cd /root/nerve-attended-source
PYTHONPATH=src:scripts python3 - <<'CHECK'
import json,hashlib
from pathlib import Path
import run_scientific_family_b_study as historical
from unittest.mock import patch
with patch.object(historical.transport,'network',side_effect=AssertionError('restore has no model calls')):
 assert historical.verify(Path('/root/nerve-attended-calibration'))['attempts']==5
bank=Path('/root/nerve-attended-bank-v3')
assert hashlib.sha256((bank/'manifest.json').read_bytes()).hexdigest()=='5095941f6aa42b369bcd72dece08406ee87290ea7c56e71ca5e1017c738afa43'
for name in ('private-seed.json','holdout.json','slice1.json','slice2.json','slice3.json'):
 assert (bank/name).stat().st_mode&0o777==0,name
assert len(list(Path('/root/nerve-attended-budget').glob('call-*.json')))==5
print(json.dumps({'restored':True,'bank_sealed':True,'prior_physical_claims':5,'historical_calibration_replay':True,'model_calls':0}),flush=True)
CHECK
