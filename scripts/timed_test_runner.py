#!/usr/bin/env python3
"""Single-process unittest tiers, with child-safe main guard and measured timing."""
import argparse
from collections import defaultdict
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import platform
import sys
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
VERSION='unittest-timing-v1'


def canonical(value):return json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n'
def digest(path):return sha256(Path(path).read_bytes()).hexdigest()
def flatten(suite):
    for test in suite:
        if isinstance(test,unittest.TestSuite):yield from flatten(test)
        else:yield test


def atomic_json(path,value):
    path=Path(path);temporary=path.with_name(path.name+f'.{os.getpid()}.tmp')
    with temporary.open('x',encoding='utf-8') as stream:
        stream.write(canonical(value));stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)


class TimedResult(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.timings=[];self.started={};self.outcomes={};self.identities={}
    def identity(self,test):
        key=id(test)
        if key not in self.identities:self.identities[key]=test.id() if callable(getattr(test,'id',None)) else str(test)
        return self.identities[key]
    def startTest(self,test):
        self.started[self.identity(test)]=time.monotonic();self.outcomes[self.identity(test)]='unknown';super().startTest(test)
    def stopTest(self,test):
        elapsed=time.monotonic()-self.started.pop(self.identity(test))
        self.timings.append({'id':self.identity(test),'module':test.__class__.__module__,'seconds':elapsed,'outcome':self.outcomes[self.identity(test)]})
        super().stopTest(test)
    def addSuccess(self,test):self.outcomes[self.identity(test)]='passed';super().addSuccess(test)
    def addError(self,test,error):self.outcomes[self.identity(test)]='error';super().addError(test,error)
    def addFailure(self,test,error):self.outcomes[self.identity(test)]='failed';super().addFailure(test,error)
    def addSkip(self,test,reason):self.outcomes[self.identity(test)]='skipped';super().addSkip(test,reason)
    def addExpectedFailure(self,test,error):self.outcomes[self.identity(test)]='expected_failure';super().addExpectedFailure(test,error)
    def addUnexpectedSuccess(self,test):self.outcomes[self.identity(test)]='unexpected_success';super().addUnexpectedSuccess(test)
    def addSubTest(self,test,subtest,error):
        if error is not None:self.outcomes[self.identity(test)]='failed_subtest'
        super().addSubTest(test,subtest,error)


def discover(directory):
    start=time.monotonic();suite=unittest.TestLoader().discover(str(directory),pattern='test*.py')
    tests=list(flatten(suite));ids=[test.id() for test in tests]
    if len(ids)!=len(set(ids)):raise ValueError('duplicate_test_ids')
    return tests,time.monotonic()-start


def partition(tests,tier,manifest):
    if tier=='profile':return tests
    if manifest.get('version')!='unittest-tiers-v1':raise ValueError('unknown_tier_manifest')
    slow=set(manifest['slow_modules'])
    return [test for test in tests if (test.__class__.__module__ in slow)==(tier=='slow')]


def run(tier,timings,manifest_path,*,directory=None,stream=None):
    paths=[str(ROOT/'src'),str(ROOT)]
    inherited=[p for p in os.environ.get('PYTHONPATH','').split(os.pathsep) if p]
    os.environ['PYTHONPATH']=os.pathsep.join(dict.fromkeys(paths+inherited))
    for entry in reversed(paths):
        if entry not in sys.path:sys.path.insert(0,entry)
    directory=Path(directory or ROOT/'tests')
    gate_start=time.monotonic();tests,discovery=discover(directory)
    manifest=None if tier=='profile' else json.loads(Path(manifest_path).read_text())
    selected=partition(tests,tier,manifest)
    known_modules={test.__class__.__module__ for test in tests}
    if tier=='slow' and set(manifest['slow_modules'])-known_modules:raise ValueError('slow_modules_missing_reprofile_required')
    module_sources={}
    for test in tests:
        module=test.__class__.__module__;source=getattr(sys.modules.get(module),'__file__',None)
        if source and Path(source).is_file():module_sources[module]={'path':str(Path(source).resolve()),'sha256':digest(source)}
    identities={id(test):test.id() for test in tests}
    selected_ids=[identities[id(test)] for test in selected]
    discovered_ids=[identities[id(test)] for test in tests]
    def make_result(*args,**kwargs):
        result=TimedResult(*args,**kwargs);result.identities=dict(identities);return result
    start=time.monotonic()
    result=unittest.TextTestRunner(stream=stream or sys.stderr,verbosity=2,resultclass=make_result).run(unittest.TestSuite(selected))
    suite_seconds=time.monotonic()-start
    measured_ids=[row['id'] for row in result.timings]
    coverage=sorted(measured_ids)==sorted(selected_ids) and len(measured_ids)==len(set(measured_ids))
    report=dict(version=VERSION,tier=tier,python=platform.python_version(),platform=platform.platform(),
        execution_model='One serial unittest runner; existing test fixtures may launch their own child processes.',
        discovered_ids=discovered_ids,selected_ids=selected_ids,module_sources=module_sources,
        discovery_seconds=discovery,suite_seconds=suite_seconds,gate_seconds=time.monotonic()-gate_start,
        fixture_and_runner_seconds=max(0,suite_seconds-sum(row['seconds'] for row in result.timings)),
        tests=result.timings,tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),
        skipped=len(result.skipped),expected_failures=len(result.expectedFailures),unexpected_successes=len(result.unexpectedSuccesses),
        complete_coverage=coverage,successful=result.wasSuccessful() and coverage,
        runner_sha256=digest(__file__))
    report['slowest_20']=sorted(report['tests'],key=lambda row:(-row['seconds'],row['id']))[:20]
    atomic_json(timings,report)
    return 0 if report['successful'] else 1


def freeze(profile_path,manifest_path,*,fast_budget_seconds=120):
    """Freeze a module partition from a successful complete measured profile."""
    if type(fast_budget_seconds) is not int or not 1<=fast_budget_seconds<180:raise ValueError('fast_budget_must_leave_margin')
    profile_path=Path(profile_path);report=json.loads(profile_path.read_text())
    if (report['version']!=VERSION or report['tier']!='profile' or report['successful'] is not True
            or report['complete_coverage'] is not True or report['failures'] or report['errors'] or report['unexpected_successes']
            or sorted(report['selected_ids'])!=sorted(report['discovered_ids'])
            or sorted(row['id'] for row in report['tests'])!=sorted(report['discovered_ids'])
            or len(set(report['discovered_ids']))!=len(report['discovered_ids'])
            or report['runner_sha256']!=digest(__file__)):
        raise ValueError('successful_complete_current_profile_required')
    costs=defaultdict(float)
    for row in report['tests']:
        if type(row['seconds']) not in (int,float) or not math.isfinite(row['seconds']) or row['seconds']<0:
            raise ValueError('finite_measured_duration_required')
        costs[row['module']]+=row['seconds']
    for source in report['module_sources'].values():
        if digest(source['path'])!=source['sha256']:raise ValueError('test_source_changed_reprofile_required')
    overhead=report['discovery_seconds']+report['fixture_and_runner_seconds']
    remaining=sum(costs.values())+overhead;slow=[]
    for module,seconds in sorted(costs.items(),key=lambda row:(-row[1],row[0])):
        if remaining<=fast_budget_seconds:break
        slow.append(module);remaining-=seconds
    if remaining>fast_budget_seconds:raise ValueError('profile_overhead_exceeds_fast_budget')
    slow_estimate=sum(costs[module] for module in slow)+overhead
    timeout=math.ceil(slow_estimate*1.5+60)
    if timeout>1800:raise ValueError('slow_timeout_exceeds_supported_bound')
    manifest=dict(version='unittest-tiers-v1',profile_sha256=digest(profile_path),slow_modules=sorted(slow),
        fast_modules_measured=sorted(set(costs)-set(slow)),new_modules_default='fast',
        measured_module_seconds=dict(sorted(costs.items())),measured_overhead_seconds=overhead,
        fast_budget_seconds=fast_budget_seconds,fast_estimated_seconds=remaining,fast_timeout_seconds=180,
        slow_estimated_seconds=slow_estimate,slow_timeout_seconds=max(1,timeout),
        selection_rule='Move largest measured modules to slow until total fast plus all measured overhead <= budget.',
        profile_tests=len(report['tests']),profile_skipped=report['skipped'])
    atomic_json(manifest_path,manifest)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('profile','fast','slow','freeze'))
    parser.add_argument('--timings');parser.add_argument('--manifest',default=str(ROOT/'tests/suite_tiers.json'))
    parser.add_argument('--profile');parser.add_argument('--fast-budget-seconds',type=int,default=120)
    args=parser.parse_args()
    if args.mode=='freeze':
        if not args.profile:parser.error('--profile required for freeze')
        print(canonical(freeze(args.profile,args.manifest,fast_budget_seconds=args.fast_budget_seconds)),end='');return 0
    if not args.timings:parser.error('--timings required for test execution')
    return run(args.mode,args.timings,args.manifest)


if __name__=='__main__':raise SystemExit(main())
