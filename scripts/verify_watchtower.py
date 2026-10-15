"""Bounded local comparison; synthetic metadata, actual NERVE AST operation."""
import json
from pathlib import Path
import sqlite3
import statistics
import tempfile
import threading
import time
from nerve_awim.repository_agents_v20 import ast_inventory
from nerve_guardian.telemetry import SQLiteMetadataSource,BoundedCollector


def measure():
    source='class Example:\n def method(self): return 1\ndef public(): return 2\n'
    with tempfile.TemporaryDirectory() as directory:
        database=Path(directory)/'application.db'
        with sqlite3.connect(database) as con:
            con.execute('CREATE TABLE gl_events(tenant TEXT,event TEXT)')
            con.executemany('INSERT INTO gl_events VALUES(?,?)',[('benchmark','synthetic')]*10000)
        samples={'baseline':[],'passive_collector':[]};successes=0;health=[]
        for trial in range(12):
            for mode in (('baseline','passive_collector') if trial%2==0 else ('passive_collector','baseline')):
                collector=None;stop=threading.Event();worker=None
                if mode=='passive_collector':
                    collector=BoundedCollector([SQLiteMetadataSource(database,tenant='benchmark',source='metadata')]).start()
                    def collect():
                        while not stop.is_set():collector.submit('metadata');collector.drain();stop.wait(.005)
                    worker=threading.Thread(target=collect);worker.start()
                started=time.perf_counter()
                for _ in range(500):
                    if ast_inventory(source)!=['public']:raise AssertionError('NERVE behavior changed')
                    successes+=1
                samples[mode].append((time.perf_counter()-started)/500)
                if collector:
                    stop.set();worker.join();health.append(collector.health());collector.stop()
        baseline=statistics.median(samples['baseline']);observed=statistics.median(samples['passive_collector'])
        return {'synthetic_metadata':True,'actual_operation':'nerve_awim.repository_agents_v20.ast_inventory',
                'successful_inventories':successes,'paired_blocks':12,'calls_per_block':500,'samples_seconds_per_call':samples,
                'median_baseline_seconds':baseline,'median_with_collector_seconds':observed,
                'relative_median_change':(observed-baseline)/baseline,'collector_health':health,
                'production_latency_cost_false_positive_false_negative_rates':'not established',
                'limitations':['local short-duration CPU fixture','separate-process production overhead not measured','not a statistical non-inferiority claim']}


if __name__=='__main__':print(json.dumps(measure(),indent=2))
