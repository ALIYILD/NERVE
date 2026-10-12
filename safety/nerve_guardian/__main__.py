"""Separately deployed Watchtower and Guardian commands; no NERVE runtime hooks."""
import argparse
import json
import os
from pathlib import Path
import signal
import threading
import time
from .store import Store,canonical


def read_config(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>65536:
        raise ValueError('bounded regular configuration required')
    if path.stat().st_mode & 0o022:raise PermissionError('configuration must not be group/world writable')
    config=json.loads(path.read_text())
    if not isinstance(config,dict):raise ValueError('configuration object required')
    return config


def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    temporary=path.with_suffix('.pending')
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as out:
        out.write(canonical(value)+'\n');out.flush();os.fsync(out.fileno())
    os.replace(temporary,path)


def build_guardian(config,*,allow_live=False):
    from .core import Guardian
    from .infrastructure import SystemdController,ManagedUnit
    from .probes import InfrastructureProbe
    from .notifications import Notifier,HTTPSDelivery
    armed=config.get('armed',False)
    if type(armed) is not bool or (armed and not allow_live):raise PermissionError('live enforcement requires explicit independent operator activation')
    if armed and os.geteuid()!=0:raise PermissionError('live controller requires separate administrator identity')
    tenants=config['tenants']
    inventory={tenant:[ManagedUnit(**unit) for unit in entry['units']] for tenant,entry in tenants.items()}
    store=Store(config['state_directory'],config['anchor_directory'])
    controller=SystemdController(inventory,config['enforcement_directory'],enabled=armed)
    probe=InfrastructureProbe(controller,protected_files={t:e.get('protected_files',{}) for t,e in tenants.items()},
                              heartbeats={t:e['watchtower_report'] for t,e in tenants.items() if 'watchtower_report' in e})
    adapters={}
    for channel,entry in config.get('notifications',{}).items():
        adapters[channel]=HTTPSDelivery(channel=channel,allowed_uids={0,os.geteuid()},**entry)
    notifier=Notifier(store.directory/'notifications.sqlite3',adapters) if adapters else None
    guardian=Guardian(store,controller,probe,tenants=tenants,owners=config.get('owners',{}),notifier=notifier,
                      armed=armed,dashboard_url=config.get('dashboard_url'))
    return guardian


def telemetry_report(path,tenant,allowed_sources=(),analyzer=None):
    try:
        path=Path(path)
        if path.is_symlink() or path.stat().st_size>262144:raise ValueError()
        value=json.loads(path.read_text())
        # This remains advisory application telemetry, even if the JSON claims otherwise.
        from .analysis import BehaviourAnalysis
        observations=value['observations']
        if not isinstance(observations,list) or len(observations)>128:raise ValueError()
        results=[]
        for obs in observations:
            if not isinstance(obs,dict) or obs.get('tenant')!=tenant or obs.get('source') not in allowed_sources:continue
            from .telemetry import _TABLES
            if not isinstance(obs.get('counters'),dict) or not set(obs['counters']).issubset(_TABLES):continue
            analysis=(analyzer or BehaviourAnalysis()).observe(obs)
            counters=obs.get('counters',{}) if analysis['risk']!='UNKNOWN' else {}
            results.append({'tenant':tenant,'source':str(obs.get('source','unknown'))[:80],
                'observed_at':obs.get('observed_at') if analysis['risk']!='UNKNOWN' else None,
                'status':analysis['risk'],'counters':counters,'source_type':'application_untrusted',
                'gaps':['independent_activity_completeness_unverified']})
        return results
    except (OSError,ValueError,KeyError,TypeError):return []


def run_service(config,*,once=False,allow_live=False):
    from .auth import OwnerVerifier
    from .web import create_server
    engine=build_guardian(config,allow_live=allow_live)
    from .analysis import BehaviourAnalysis
    analyzer=BehaviourAnalysis()
    stop=threading.Event();server=None
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.set())
    try:
        identity=config.get('identity')
        if identity:
            verifier=OwnerVerifier(public_keys={kid:Path(path).read_text() for kid,path in identity['public_key_files'].items()},
                                   issuer=identity['issuer'],audience=identity['audience'],owners=config['owners'],mfa_acr=identity.get('mfa_acr',[]))
            server=create_server(engine,verifier,port=config.get('portal_port',8787))
            threading.Thread(target=server.serve_forever,daemon=True).start()
        interval=config.get('interval_seconds',5)
        if type(interval) not in (int,float) or not .25<=interval<=60:raise ValueError('bounded interval required')
        while not stop.is_set():
            statuses={}
            for tenant,entry in config['tenants'].items():
                engine.telemetry[tenant]=telemetry_report(entry['watchtower_report'],tenant,entry.get('telemetry_sources',[]),analyzer) if 'watchtower_report' in entry else []
                statuses[tenant]=engine.tick(tenant)
            # Independent external monitor must read this from another trust boundary.
            atomic_json(Path(config['state_directory'])/'guardian-health.json',{'timestamp':time.time(),'status':'UNKNOWN' if any(s.get('visibility')=='UNKNOWN' or s.get('risk')=='UNKNOWN' for s in statuses.values()) else 'OBSERVED_SCOPE_ONLY',
                'tenants':{t:{'risk':s['risk'],'state':s['emergency_state']} for t,s in statuses.items()}})
            if once:return statuses
            enhanced=any(i.get('increased_monitoring_until',0)>time.time() for s in statuses.values() for i in s.get('incidents',[]))
            stop.wait(min(interval,1) if enhanced else interval)
    finally:
        if server:server.shutdown();server.server_close()
        if engine.notifier:engine.notifier.close()


def run_watchtower(config,*,once=False):
    from .telemetry import SQLiteMetadataSource,BoundedCollector
    from .analysis import BehaviourAnalysis
    sources=[SQLiteMetadataSource(**source) for source in config['sources']]
    collector=BoundedCollector(sources).start();analysis=BehaviourAnalysis();stop=threading.Event()
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.set())
    interval=config.get('interval_seconds',5)
    if type(interval) not in (float,int) or not .25<=interval<=60:raise ValueError('bounded interval required')
    observations={}
    try:
        while not stop.is_set():
            for source in collector.sources:collector.submit(source)
            # Watchtower is independent; bounded wait never touches NERVE's path.
            stop.wait(min(interval,2.2))
            for item in collector.drain():
                item['analysis']=analysis.observe(item);observations[item['source']]=item
            atomic_json(config['report_path'],{'timestamp':time.time(),'health':collector.health(),'observations':list(observations.values())})
            if once:return {'sources':len(sources),'health':collector.health()}
            stop.wait(interval)
    finally:collector.stop()


def main():
    parser=argparse.ArgumentParser(description='Independent Watchtower/Guardian; observe-only by default')
    parser.add_argument('command',choices=['demo','watchtower','service','validate'])
    parser.add_argument('--config',type=Path);parser.add_argument('--report',type=Path)
    parser.add_argument('--once',action='store_true')
    parser.add_argument('--allow-live-enforcement',action='store_true',help='Independent infrastructure administrator only; never use during development')
    args=parser.parse_args()
    if args.command=='demo':
        from .demo import run_demo
        result=run_demo()
    else:
        if not args.config:parser.error('--config required')
        config=read_config(args.config)
        if args.command=='validate':
            if config.get('armed',False):raise PermissionError('development configuration must be observe-only')
            result={'valid_json':True,'armed':False,'production_readiness':'unverified'}
        elif args.command=='watchtower':result=run_watchtower(config,once=args.once)
        else:result=run_service(config,once=args.once,allow_live=args.allow_live_enforcement)
    if args.report:atomic_json(args.report,result)
    print(json.dumps(result,indent=2,allow_nan=False))


if __name__=='__main__':main()
