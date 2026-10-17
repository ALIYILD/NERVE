#!/usr/bin/env python3
"""Sanitize a saved RunPod MCP list-pods response; no credentials persisted."""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path

def sanitize(data):
    if 'content' in data:
        data=json.loads(next(x['text'] for x in data['content'] if x['type']=='text'))
    if data.get('pagination',{}).get('hasNextPage'):
        raise ValueError('incomplete inventory; fetch all pages before acting')
    return {'observed_at':datetime.now(timezone.utc).isoformat(),'pods':[{'id':p['id'],'status':p['status'],'gpu':p.get('gpu',{}).get('id'),'region':p.get('dataCenterId'),'hourly_usd':p['cost'],'started_at':p.get('startedAt'),'assigned_role':None} for p in data['pods']]}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.write_text(json.dumps(sanitize(json.loads(a.input.read_text())),indent=2)+'\n')
