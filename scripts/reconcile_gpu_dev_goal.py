"""Record a public GPU-development verifier verdict; never dispatch inference."""
import argparse
import hashlib
import json
from pathlib import Path

from nerve_awim.goal_orchestrator import GoalOrchestrator
from nerve_awim.memory_gateway import scientific_gpu_dev_study as study
from run_scientific_gpu_dev_study import install_development_file_guard


def build_goal(state, protocol, report_digest, verify):
    root=Path(state)
    root.mkdir(parents=True,exist_ok=True)
    binding={'protocol':protocol,'report_sha256':report_digest,
             'verifier_sources':study.sources(),
             'orchestrator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             'target':'Verify registered dev evaluation; keep selection and promotion distinct'}
    encoded=json.dumps(binding,sort_keys=True,separators=(',',':'))+'\n'
    path=root/'binding.json'
    if path.exists():
        if path.read_text()!=encoded:raise ValueError('goal_binding_changed')
    else:
        with path.open('x') as stream:stream.write(encoded)
    def evaluate(_context):
        report=verify()
        if (hashlib.sha256((json.dumps(report,sort_keys=True,separators=(',',':'))+'\n').encode()).hexdigest()
                !=report_digest):raise ValueError('verified_report_changed')
        if report.get('status')!='complete' or report.get('protocol')!=protocol:
            raise ValueError('registered_complete_report_required')
        if any(report.get(k) is not False for k in ('holdout_accessed','promotion_authorized','model_weights_trained','efficacy_established')):
            raise ValueError('scope_violation')
        summary=report['summary']
        return {'verified':True,'verdict':summary['verdict'],
                'candidate_selected_for_review':summary['prospective_gate_passed'],
                'generalization_verdict':summary['generalization_verdict'],
                'promotion_authorized':False,'retained_skill_selected':False,'new_model_calls':0}
    goal=GoalOrchestrator(root,handlers={'verify':evaluate},validators={'verify':lambda r:r.get('verified') is True})
    if not goal.path.exists():
        goal.create(goal_id='gpu-dev-'+hashlib.sha256(encoded.encode()).hexdigest(),
            target=binding['target'],tasks=[{'id':'canonical-development-verification','handler':'verify'}],deadline_seconds=300)
    return goal


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',required=True);parser.add_argument('--state',required=True)
    args=parser.parse_args()
    directory=Path(args.study).resolve()
    protocol=json.loads((directory/'preregistration.json').read_text())
    install_development_file_guard(protocol['paths']['bank_directory'])
    digest=hashlib.sha256((directory/'report.json').read_bytes()).hexdigest()
    def verify():
        return study.validate_receipt(directory,protocol['expected_digest'],protocol['journal'],**protocol['paths'])
    result=build_goal(args.state,protocol,digest,verify).run()
    print(json.dumps(result,sort_keys=True,indent=2))
    return 0 if result['status']=='complete' else 1


if __name__=='__main__':raise SystemExit(main())
