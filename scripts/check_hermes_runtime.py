"""Probe real Hermes import/construction in its isolated PM environment.

No conversation is run. Python socket connections are rejected, not sandboxed:
the host must still isolate the process from secrets and untrusted plugins.
"""
import argparse
import json
import sys
from nerve_awim.hermes_agents import HERMES_REVISION, load_pinned_factory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--checkout', required=True)
    args = parser.parse_args()
    blocked = []
    def audit(event, arguments):
        if event == 'socket.connect':
            blocked.append(event)
            raise RuntimeError('network disabled during Hermes readiness probe')
    sys.addaudithook(audit)
    report = {'revision':HERMES_REVISION, 'python':sys.version.split()[0],
              'imported':False, 'constructed':False, 'model_calls':0}
    agent = None
    try:
        factory = load_pinned_factory(args.checkout, enabled=True)
        report['imported'] = True
        agent = factory(model='offline-contract', provider='openai',
            base_url='http://127.0.0.1:1/v1', api_key='offline-placeholder',
            enabled_toolsets=[], max_iterations=2, max_tokens=2048,
            skip_memory=True, skip_context_files=True, skip_background_review=True,
            load_soul_identity=False, save_trajectories=False,
            verbose_logging=False, quiet_mode=True, run_budget_seconds=60)
        report['constructed'] = True
        report['tool_count'] = len(agent.tools)
        if agent.tools:
            raise RuntimeError('unexpected tools in text-only runtime')
        report['status'] = 'ready_for_isolated_provider_test'
        code = 0
    except Exception as error:
        report['status'] = 'blocked'
        report['error_type'] = type(error).__name__
        # Exception values can include environment paths/config. Keep the report
        # categorical; diagnosis is performed in the isolated provisioning log.
        code = 1
    finally:
        if agent is not None:
            agent.close()
    report['blocked_python_connections'] = len(blocked)
    print(json.dumps(report, indent=2))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
