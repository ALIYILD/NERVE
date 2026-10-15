"""Bounded synthetic exercise with a real, disposable child process.

This does not establish host administration separation, Linux systemd enforcement,
live identity, or provider delivery. It never targets an existing workload.
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from .auth import Principal
from .core import Guardian
from .store import Store
from .notifications import Notifier


class DisposableController:
    def __init__(self,directory):
        self.directory=Path(directory);self.block=self.directory/'demo-latch.json'
        self.process=None;self.actions=[]
        self.start()

    def start(self):
        if self.block.exists():raise PermissionError('external supervisor restart latch')
        # Known dummy workload only: ignores application/TERM shutdown and waits.
        self.process=subprocess.Popen([sys.executable,'-c',
            'import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);print("ready",flush=True);time.sleep(120)'],
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,start_new_session=True,text=True)
        if self.process.stdout.readline().strip()!='ready':raise RuntimeError('fixture failed')

    def contain(self,tenant,incident_id):
        self.block.write_text(json.dumps({'incident_id':incident_id,'latched':True}))
        if self.process and self.process.poll() is None:
            os.killpg(self.process.pid,signal.SIGKILL);self.process.wait(timeout=3)
            self.process.stdout.close()
        self.actions.append({'action':'kill_disposable_process_group','verified':True})
        return {**self.verify(tenant),'actions':self.actions[-1:]}

    def verify(self,tenant):
        stopped=self.process is None or self.process.poll() is not None
        return {'verified':stopped and self.block.exists(),'coverage':[{'unit':'disposable-demo-child','stopped':stopped,'masked':self.block.exists()}],
                'gaps':['synthetic_supervisor_not_systemd','same_user_fixture_not_privilege_isolation']}

    def restart(self,tenant,incident_id):
        if not self.block.exists() or json.loads(self.block.read_text())['incident_id']!=incident_id:raise PermissionError('incident mismatch')
        self.block.unlink();self.start()
        return {'verified':self.process.poll() is None,'coverage':['disposable-demo-child']}

    def close(self):
        if self.process and self.process.poll() is None:
            os.killpg(self.process.pid,signal.SIGKILL);self.process.wait(timeout=3)
        if self.process and self.process.stdout:self.process.stdout.close()


class FixtureProbe:
    def __init__(self,path):
        self.path=Path(path);self.expected=hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.unknown=False

    def sample(self,tenant):
        actual=hashlib.sha256(self.path.read_bytes()).hexdigest()
        kinds=['protected_file_intact','observer_heartbeat','workload_state','execution_permissions','deployment_provenance']
        result=[{'kind':k,'source':'synthetic-admin-fixture','observed_at':time.time(),'status':'NORMAL','independent':True} for k in kinds]
        if actual!=self.expected:
            result[0].update(kind='protected_file_changed',status='CRITICAL',evidence={'file':self.path.name,'sha256':actual,'expected':self.expected})
        if self.unknown:result[-1]['status']='UNKNOWN'
        return result


def run_demo():
    with tempfile.TemporaryDirectory(prefix='nerve-watchtower-demo-') as directory:
        root=Path(directory);protected=root/'protected-config';protected.write_text('approved')
        controller=DisposableController(root);deliveries=[]
        notifier=Notifier(root/'alerts.sqlite3',{'telegram':lambda a:deliveries.append(('telegram',time.monotonic())),
                                             'email':lambda a:deliveries.append(('email',time.monotonic()))},rate_seconds=0)
        try:
            probe=FixtureProbe(protected);store=Store(root/'guardian',root/'anchor')
            engine=Guardian(store,controller,probe,tenants=['demo'],owners={'test-owner':'demo'},notifier=notifier,
                            armed=True,synthetic=True,dashboard_url='https://guardian.example.invalid/')
            normal=engine.tick('demo');normal_alive=controller.process.poll() is None
            protected.write_text('tampered');start=time.monotonic();incident=engine.tick('demo')['incidents'][0]
            stopped_latency=time.monotonic()-start
            try:controller.start();recreation_blocked=False
            except PermissionError:recreation_blocked=True
            protected.write_text('approved')
            now=int(time.time())
            principal=Principal('test-owner','demo',now,'synthetic-request-identity',now+300)
            request=engine.request_restart(principal,incident['id'],'synthetic-remediation')
            result=engine.approve_restart(Principal('test-owner','demo',now,'synthetic-approval-identity',now+300),incident['id'],request['id'])
            try:engine.approve_restart(principal,incident['id'],request['id']);replay_denied=False
            except PermissionError:replay_denied=True
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                rows=notifier.status('demo')
                if len(rows)>=10 and all(r['status']=='accepted' for r in rows):break
                time.sleep(.02)
            return {'synthetic':True,'live_provider_calls':0,'normal_workload_alive':normal_alive,'normal_visibility':normal['visibility'],
                'critical_trigger':'actual_fixture_file_hash_changed','containment_status':incident['containment_status'],
                'real_disposable_process_stopped':incident['verification_status']=='verified','recreation_blocked':recreation_blocked,
                'restart_status':result['status'],'replay_denied':replay_denied,'detection_to_verified_stop_seconds':stopped_latency,
                'notification_channels_exercised':sorted({c for c,_ in deliveries}),'notification_fixture_status':notifier.status('demo'),
                'first_fixture_notification_seconds':min((t-start for _,t in deliveries),default=None),
                'audit_records':len(store.audit('demo')),'limitations':['synthetic_MFA_principals','fixture_notification_adapters','no_live_systemd_or_IAM','same_OS_user_not_production_isolation']}
        finally:notifier.close();controller.close()
