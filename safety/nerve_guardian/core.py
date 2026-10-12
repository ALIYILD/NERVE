"""Independent incident orchestration; there is no application telemetry ingress.

Only the configured infrastructure probe can supply critical observations. This
service must be deployed outside agent credentials and writable code boundaries.
"""
import copy
from datetime import datetime,timezone
import fcntl
import math
import os
import re
import threading
import time
import uuid
from contextlib import contextmanager
from .store import IntegrityError

CRITICAL_KINDS=frozenset({'protected_file_changed','unauthorized_restart'})
ACTIVE=frozenset({'CONTAINING','AWAITING_OWNER_REVIEW','PARTIAL_CONTAINMENT','RESTARTING','RESTART_DENIED'})


def label(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}',value):
        raise ValueError('bounded reference required')
    return value


class Guardian:
    def __init__(self, store, controller, probe, *, tenants, owners, notifier=None,
                 clock=time.time, armed=False, synthetic=False, max_age=30, dashboard_url=None):
        self.store,self.controller,self.probe=store,controller,probe
        self.tenants=tuple(label(t) for t in tenants)
        if not self.tenants or len(set(self.tenants))!=len(self.tenants):raise ValueError('unique tenants required')
        self.owners={label(k):label(v) for k,v in owners.items()}
        self.notifier,self.clock,self.armed,self.synthetic=notifier,clock,armed,synthetic
        self.dashboard_url=dashboard_url
        self.max_age=max_age
        self.required_restart_kinds=frozenset({'protected_file_intact','observer_heartbeat','workload_state','execution_permissions','deployment_provenance'})
        self.latest={};self.telemetry={};self.lock=threading.RLock()

    @contextmanager
    def exclusive(self):
        with self.lock:
            fd=os.open(self.store.directory/'controller.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
            try:
                fcntl.flock(fd,fcntl.LOCK_EX);yield
            finally:fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)

    def _tenant(self,tenant):
        if tenant not in self.tenants:raise PermissionError('unknown tenant')

    def _sample(self,tenant):
        now=self.clock()
        try:observations=self.probe.sample(tenant)
        except Exception:observations=[]
        now=self.clock()
        result=[]
        if not isinstance(observations,list) or len(observations)>128:observations=[]
        for obs in observations:
            if not isinstance(obs,dict):continue
            stamp=obs.get('observed_at')
            fresh=type(stamp) in (float,int) and math.isfinite(stamp) and 0<=now-stamp<=self.max_age
            try:kind=label(obs.get('kind'));source=label(obs.get('source'))
            except ValueError:continue
            status=obs.get('status') if fresh and obs.get('independent') is True else 'UNKNOWN'
            if status not in ('OK','NORMAL','WARNING','CRITICAL','UNKNOWN'):status='UNKNOWN'
            # Evidence is a bounded categorical reference, never arbitrary sensor text.
            result.append({'source':source,'kind':kind,'status':status,'observed_at':stamp if fresh else None,
                           'independent':obs.get('independent') is True,
                           'evidence':self._evidence(obs.get('evidence',{}))})
        if not result:result=[{'source':'guardian','kind':'visibility_loss','status':'UNKNOWN','observed_at':now,'independent':True}]
        self.latest[tenant]=result
        return result

    @staticmethod
    def _evidence(raw):
        if not isinstance(raw,dict):return {}
        result={}
        for key in ('file','unit','sha256','expected','latched','stopped','masked','signal'):
            value=raw.get(key)
            if type(value) is bool:result[key]=value
            elif isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}',value):result[key]=value
        return result

    def _independent_alarm(self,tenant,event):
        if self.notifier is None:return
        try:self.notifier.enqueue({'tenant':tenant,'incident_id':event+'-'+str(int(self.clock()//300)),
            'event':event,'severity':'WARNING','timestamp':self.clock(),'containment_status':'UNKNOWN',
            'verification_status':'unknown','evidence_reference':event,'next_action_code':'independent_operator_review'})
        except Exception:pass

    def _emergency_contain(self,tenant):
        # Independent evidence can still stop a threat when the primary audit is
        # unavailable. Preserve an emergency receipt outside that damaged store.
        from .store import canonical
        path=self.store.anchor_directory/('emergency-'+tenant+'.json')
        try:
            if path.exists():
                import json
                incident=json.loads(path.read_text())['incident_id']
            else:
                latch=self.controller.latch(tenant) if hasattr(self.controller,'latch') else None
                incident=latch['incident_id'] if latch and latch.get('latched') else uuid.uuid4().hex
                fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                with os.fdopen(fd,'w') as out:
                    out.write(canonical({'incident_id':incident,'tenant':tenant,'timestamp':self.clock(),'reason':'critical_with_audit_failure'}))
                    out.flush();os.fsync(out.fileno())
            self.controller.contain(tenant,incident)
        except Exception:self._independent_alarm(tenant,'emergency_containment_unverified')

    def _alert(self,state,incident,event,severity='CRITICAL'):
        key=incident['tenant']+':'+incident['id']+':'+event
        state['notifications'][key]={'tenant':incident['tenant'],'incident_id':incident['id'],'event':event,
            'severity':severity,'timestamp':self.clock(),'containment_status':incident['containment_status'],
            'verification_status':incident['verification_status'],'evidence_reference':incident['trigger'],
            'next_action_code':'owner_review_required'}
        state['notifications'][key]['timestamp_utc']=datetime.fromtimestamp(self.clock(),timezone.utc).isoformat()
        units=[o.get('evidence',{}).get('unit') for o in self.latest.get(incident['tenant'],[]) if o.get('evidence',{}).get('unit')]
        state['notifications'][key]['affected_service']=','.join(dict.fromkeys(units))[:512] or 'configured-managed-scope'
        if self.dashboard_url:state['notifications'][key]['dashboard_url']=self.dashboard_url

    def _flush(self):
        if self.notifier is None:return
        state=self.store.read()
        for alert in list(state['notifications'].values())[-1024:]:
            try:self.notifier.enqueue(alert)
            except Exception:pass  # Durable intents are retried independently of containment.

    def _contain(self,incident):
        try:result=self.controller.contain(incident['tenant'],incident['id'])
        except Exception:result={'verified':False,'actions':[],'coverage':[],'gaps':['controller_unavailable']}
        # Always read the supervisor again, even if a stop request returned success.
        try:verification=self.controller.verify(incident['tenant'])
        except Exception:verification={'verified':False,'coverage':[],'gaps':['verification_unavailable']}
        confirmed=result.get('verified') is True and verification.get('verified') is True
        def complete(state):
            item=state['incidents'][incident['id']]
            item.update(status='AWAITING_OWNER_REVIEW' if confirmed else 'PARTIAL_CONTAINMENT',
                containment_status='SHUTDOWN_CONFIRMED' if confirmed else 'PARTIAL_CONTAINMENT',
                verification_status='verified' if confirmed else 'incomplete',
                enforcement=result,verification=verification,updated_at=self.clock(),attempts=item['attempts']+1)
            self._alert(state,item,'shutdown_verified' if confirmed else 'partial_containment')
            return item
        return self.store.change(incident['tenant'],'containment_result',complete)

    def tick(self,tenant):
        self._tenant(tenant)
        with self.exclusive():
            observations=self._sample(tenant)
            # Broken audit cannot authorize restart or claim normality. Its separate
            # health signal is exposed even when the incident store is unavailable.
            try:state=self.store.read()
            except IntegrityError:
                self.latest[tenant].append({'source':'guardian','kind':'audit_integrity','status':'UNKNOWN','observed_at':self.clock(),'independent':True})
                self._independent_alarm(tenant,'audit_integrity_failure')
                if self.armed and any(o['status']=='CRITICAL' and o['kind'] in CRITICAL_KINDS for o in observations):
                    self._emergency_contain(tenant)
                return {'risk':'UNKNOWN','emergency_state':'AUDIT_INTEGRITY_FAILURE'}
            critical=[o for o in observations if o['status']=='CRITICAL' and o['kind'] in CRITICAL_KINDS]
            active=next((i for i in state['incidents'].values() if i['tenant']==tenant and i['status'] in ACTIVE|{'OBSERVED_UNARMED'}),None)
            if critical and active is None:
                ident=uuid.uuid4().hex
                def create(state):
                    incident={'id':ident,'tenant':tenant,'trigger':critical[0]['kind'],'observations':critical,
                        'created_at':self.clock(),'updated_at':self.clock(),'status':'CONTAINING' if self.armed else 'OBSERVED_UNARMED',
                        'containment_status':'INITIATED' if self.armed else 'DISABLED','verification_status':'pending',
                        'attempts':0,'synthetic':self.synthetic}
                    state['incidents'][ident]=incident;self._alert(state,incident,'critical_incident')
                    if self.armed:self._alert(state,incident,'shutdown_initiated')
                    return incident
                active=self.store.change(tenant,'critical_incident',create)
            if self.armed and critical and active is not None and active['status']=='OBSERVED_UNARMED':
                def activate(state):
                    item=state['incidents'][active['id']]
                    item.update(status='CONTAINING',containment_status='INITIATED',observations=critical,updated_at=self.clock())
                    self._alert(state,item,'shutdown_initiated');return item
                active=self.store.change(tenant,'verified_incident_armed',activate)
            if self.armed and active is not None and active['status'] in ('CONTAINING','PARTIAL_CONTAINMENT','RESTARTING','RESTART_DENIED'):
                active=self._contain(active)
            elif self.armed and active is not None and active['status']=='AWAITING_OWNER_REVIEW':
                try:still_stopped=self.controller.verify(tenant).get('verified') is True
                except Exception:still_stopped=False
                if not still_stopped:active=self._contain(active)
            if any(o['status']=='UNKNOWN' for o in observations):
                # Time-bucketed visibility alarms; no automatic shutdown on blindness.
                ident='visibility-'+str(int(self.clock()//300))
                def visibility(state):
                    incident={'id':ident,'tenant':tenant,'trigger':'visibility_loss','containment_status':'UNCHANGED','verification_status':'unknown'}
                    self._alert(state,incident,'visibility_loss','WARNING')
                self.store.change(tenant,'visibility_loss',visibility)
            self._flush()
            return self.snapshot(tenant)

    def _principal(self,principal):
        now=self.clock()
        if (getattr(principal,'verified_mfa',False) is not True or self.owners.get(getattr(principal,'subject',None))!=getattr(principal,'tenant',None)
                or not 0<=now-principal.auth_time<=300 or not now<principal.expires_at):
            raise PermissionError('fresh independent owner MFA required')
        label(principal.jti);self._tenant(principal.tenant)

    def _consume(self,state,principal):
        key=principal.subject+':'+principal.jti
        if key in state['tokens']:raise PermissionError('authentication replay')
        state['tokens']={k:v for k,v in state['tokens'].items() if v>self.clock()}
        state['tokens'][key]=principal.expires_at

    def request_restart(self,principal,incident_id,cause_reference):
        self._principal(principal);label(incident_id);label(cause_reference)
        with self.exclusive():
            self._principal(principal)
            def request(state):
                incident=state['incidents'].get(incident_id)
                if not incident or incident['tenant']!=principal.tenant:raise PermissionError('incident scope denied')
                if incident['status']!='AWAITING_OWNER_REVIEW':raise PermissionError('verified containment required')
                self._consume(state,principal)
                ident=uuid.uuid4().hex
                state['requests'][ident]={'id':ident,'incident_id':incident_id,'tenant':principal.tenant,'subject':principal.subject,
                    'cause_reference':cause_reference,'expires_at':self.clock()+300,'status':'pending'}
                self._alert(state,incident,'recovery_approval_requested','NOTICE')
                return state['requests'][ident]
            result=self.store.change(principal.tenant,'restart_requested',request);self._flush();return result

    def approve_restart(self,principal,incident_id,request_id):
        self._principal(principal);label(incident_id);label(request_id)
        with self.exclusive():
            self._principal(principal)
            observations=self._sample(principal.tenant)
            safe=(self.required_restart_kinds.issubset({o['kind'] for o in observations})
                  and all(o['status'] in ('OK','NORMAL') for o in observations))
            if not self.synthetic:
                try:safe=safe and self.notifier is not None and self.notifier.health()['status']=='AVAILABLE'
                except Exception:safe=False
            try:stopped=self.controller.verify(principal.tenant).get('verified') is True
            except Exception:stopped=False
            def approve(state):
                request=state['requests'].get(request_id);incident=state['incidents'].get(incident_id)
                if (not request or not incident or request['tenant']!=principal.tenant or incident['tenant']!=principal.tenant
                    or request['incident_id']!=incident_id or request['status']!='pending' or request['expires_at']<=self.clock()
                    or incident['status']!='AWAITING_OWNER_REVIEW'):
                    raise PermissionError('restart request invalid')
                self._consume(state,principal);request['status']='consumed'
                incident['status']='RESTARTING' if safe and stopped and self.armed else 'RESTART_DENIED'
                return incident
            incident=self.store.change(principal.tenant,'restart_decision',approve)
            if incident['status']!='RESTARTING':raise PermissionError('mandatory recovery checks failed')
            try:result=self.controller.restart(principal.tenant,incident_id)
            except Exception:result={'verified':False,'gaps':['restart_controller_unavailable']}
            after=self._sample(principal.tenant)
            post_safe=(self.required_restart_kinds.issubset({o['kind'] for o in after})
                       and all(o['status'] in ('OK','NORMAL') for o in after))
            if result.get('verified') is not True or not post_safe:
                # Failed partial start must be contained again before returning.
                self._contain(incident)
                raise PermissionError('restart failed; containment reapplied')
            def finish(state):
                item=state['incidents'][incident_id]
                item.update(status='RESOLVED',containment_status='AUTHORIZED_RESTART',verification_status='verified',
                            restart=result,updated_at=self.clock(),increased_monitoring_until=self.clock()+900)
                self._alert(state,item,'authorized_restart','NOTICE');return item
            result=self.store.change(principal.tenant,'authorized_restart',finish);self._flush();return result

    def keep_stopped(self,principal,incident_id):
        self._principal(principal);label(incident_id)
        with self.exclusive():
            def hold(state):
                item=state['incidents'].get(incident_id)
                if not item or item['tenant']!=principal.tenant or item['status'] not in ACTIVE:raise PermissionError('incident scope denied')
                self._consume(state,principal)
                for request in state['requests'].values():
                    if request['incident_id']==incident_id:request['status']='cancelled'
                item['owner_hold_at']=self.clock();return item
            return self.store.change(principal.tenant,'owner_keep_stopped',hold)

    def record_denial(self,tenant=None):
        # Unauthenticated attempts carry no claimed identity or submitted payload.
        # Coalesce the alert per tenant/time bucket to bound notification floods.
        targets=[tenant] if tenant in self.tenants else list(self.tenants)
        for target in targets:
            ident='restart-denied-'+str(int(self.clock()//300))
            key=target+':'+ident+':unauthorized_restart_attempt'
            try:
                if key in self.store.read()['notifications']:continue
                def denied(state):
                    item={'id':ident,'tenant':target,'trigger':'unauthorized_restart_attempt',
                          'containment_status':'UNCHANGED','verification_status':'authentication_denied'}
                    self._alert(state,item,'unauthorized_restart_attempt','WARNING')
                self.store.change(target,'unauthorized_restart_attempt',denied)
            except IntegrityError:self._independent_alarm(target,'unauthorized_restart_attempt')
        self._flush()

    def audit(self,tenant):
        self._tenant(tenant);return self.store.audit(tenant)

    def snapshot(self,tenant):
        self._tenant(tenant)
        try:
            state=self.store.read();incidents=[i for i in state['incidents'].values() if i['tenant']==tenant]
            audit_ok=True
        except IntegrityError:incidents=[];audit_ok=False
        observations=copy.deepcopy(self.latest.get(tenant,[]))
        fresh=bool(observations) and all(o['observed_at'] is not None and 0<=self.clock()-o['observed_at']<=self.max_age for o in observations)
        visibility='OBSERVED_SCOPE_ONLY' if fresh and audit_ok and all(o['status']!='UNKNOWN' for o in observations) else 'UNKNOWN'
        active=next((i for i in reversed(incidents) if i['status'] in ACTIVE),None)
        try:
            notifications=self.notifier.status(tenant) if self.notifier else []
            notification_health=self.notifier.health() if self.notifier else {'status':'UNKNOWN','reason':'not_configured'}
        except Exception:
            notifications=[];notification_health={'status':'UNKNOWN','reason':'notification_monitor_unavailable'}
        if notification_health['status']=='UNKNOWN':visibility='UNKNOWN'
        result={'schema':'nerve-guardian-v1','tenant':tenant,'timestamp':self.clock(),'synthetic':self.synthetic,
            'mode':'armed-isolated-test' if self.armed and self.synthetic else ('armed' if self.armed else 'observe-only'),
            'visibility':visibility,'risk':('CRITICAL' if active or any(o['status']=='CRITICAL' for o in observations) else
                    ('WARNING' if any(o['status']=='WARNING' for o in observations) else ('UNKNOWN' if visibility=='UNKNOWN' else 'NORMAL'))),
            'emergency_state':active['status'] if active else ('OBSERVING' if audit_ok else 'AUDIT_INTEGRITY_FAILURE'),
            'telemetry':copy.deepcopy(self.telemetry.get(tenant,[])),'observer':observations,'incidents':incidents,
            'coverage':active.get('verification',{}).get('coverage',[]) if active else [],
            'gaps':['unmanaged_workloads','external_iam_and_network_not_enforced','production_coverage_unverified'],
            'notifications':notifications,'notification_health':notification_health,'audit_integrity':'verified' if audit_ok else 'UNKNOWN'}

        def counters(tables):
            rows=[{'source':r['source'],'observed_at':r['observed_at'],'table':k,'count':v,'source_type':'application_untrusted'}
                  for r in result['telemetry'] for k,v in r.get('counters',{}).items() if k in tables]
            return {'status':'OBSERVED_METADATA_ONLY' if rows else 'UNKNOWN','measurements':rows,
                    'limitation':'aggregate application-owned counters; completeness and semantic activity unverified'}
        unknown={'status':'UNKNOWN','reason':'independent source not configured'}
        result['dashboard_sections']={
            'NERVE Overview':{k:result[k] for k in ('timestamp','mode','visibility','risk','gaps')},
            'Agent Activity':counters({'gl_tasks','adaptation_tasks'}),
            'Self-Learning Activity':counters({'gl_outcomes','gl_events'}),
            'Recursive Self-Improvement':counters({'gl_candidates','gl_releases'}),
            'Auto-Adaptation':counters({'adaptation_events','adaptation_corrections'}),
            'Tool Execution':unknown,'Memory Evolution':unknown,
            'Model and Code Changes':[o for o in observations if o['source']=='protected_files'] or unknown,
            'Network and Infrastructure':{'observations':[o for o in observations if o['source']=='systemd'],'gaps':result['gaps']},
            'Behaviour Risk':{'risk':result['risk'],'automatic_policy':'fresh independent pinned invariant only'},
            'Observer Integrity':{'observations':observations,'audit':result['audit_integrity'],'notifications':notification_health},
            'Incident Centre':incidents,'Notifications':notifications,'Emergency State':result['emergency_state'],
            'Audit Timeline':{'integrity':result['audit_integrity'],'download':'/api/audit','source':'independent_guardian_ledger'}}
        return result
