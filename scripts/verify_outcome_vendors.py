"""Verify both application integrations use the exact NERVE learner and license."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def verify(clinical_root, perfflux_root):
    result={}
    for name,root,suffix in (
        ('clinical_os',clinical_root,'apps/api/app/services/continual_learning/nerve_outcome_core'),
        ('perfflux',perfflux_root,'src/perfflux/agents/fleet/nerve_core')):
        vendor=Path(root)/suffix
        manifest=json.loads((vendor/'PROVENANCE.json').read_text())
        for filename,relative in [('outcome_forecast.py','src/nerve_awim/outcome_forecast.py'),('LICENSE','LICENSE'),('NOTICE','NOTICE')]:
            expected=(ROOT/relative).read_bytes()
            if (vendor/filename).read_bytes()!=expected or sha256(expected).hexdigest()!=manifest['sha256'][filename]:
                raise ValueError(name+' source or license drift: '+filename)
        result[name]={'verified':True,'upstream_commit':manifest['upstream_commit'],'source_sha256':manifest['sha256']['outcome_forecast.py']}
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--clinical-root',required=True,type=Path)
    p.add_argument('--perfflux-root',required=True,type=Path)
    a=p.parse_args()
    print(json.dumps(verify(a.clinical_root,a.perfflux_root),indent=2))
