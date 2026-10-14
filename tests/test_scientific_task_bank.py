"""Synthetic fixtures generated only in temporary private directories."""
from collections import Counter
from dataclasses import replace
import json
import os
import re
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from nerve_awim.memory_gateway import scientific_task_bank as s
from nerve_awim.memory_v18 import MemoryAuthority


class ScientificTaskBankTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.directory=self.root/'bank'
        self.result=s.build(self.directory,host_seed='a'*64)
        self.auth=MemoryAuthority()
        self.generator=self.auth.issue('research','generator',permissions=('read',))
        self.gate=self.auth.issue('research','selection-gate',permissions=('read','approve'))
        self.bank=s.ScientificTaskBank(self.directory,self.auth,expected_manifest_hash=self.result['manifest_sha256'],
            tenant_id='research',generator_agent_id='generator',gate_actor=self.gate)

    def test_full_bank_counts_and_strata(self):
        dev=self.bank.development(self.generator);held=self.bank.holdout(self.gate)
        self.assertEqual(len(dev),700);self.assertEqual(len(held),300)
        self.assertEqual(Counter(r['stratum'] for r in dev),dict.fromkeys(s.STRATA,100))
        self.assertTrue(all(n>=20 for n in Counter(r['stratum'] for r in held).values()))
        self.assertEqual({r['task_id'] for r in dev}&{r['task_id'] for r in held},set())
        self.assertFalse({r['query'] for r in dev}&{r['query'] for r in held})
        self.assertFalse({f['content'] for r in dev for f in r['evidence']}&{f['content'] for r in held for f in r['evidence']})
        for row in dev+held:
            s.parse(s._json(row['expected']))
            self.assertEqual(row['content_sha256'],s._hash({k:v for k,v in row.items() if k!='content_sha256'}))
            for fact in row['evidence']:
                self.assertTrue({'content','source_id','timestamp','version','current','content_sha256'}<=set(fact))

    def test_generator_read_does_not_open_holdout_file(self):
        original=s._read
        def guarded(path,limit):
            if Path(path).name=='holdout.json':raise AssertionError('generator opened holdout')
            return original(path,limit)
        with patch.object(s,'_read',side_effect=guarded):
            self.assertEqual(len(self.bank.development(self.generator)),700)

    def test_rules_current_and_agreement_exact_keys(self):
        rows=self.bank.development(self.generator)
        for row in rows:
            if row['stratum']=='stale-vs-current':
                selected=next(f for f in row['evidence'] if f['current'])
                self.assertEqual(row['expected']['source_id'],selected['source_id'])
                self.assertEqual(selected['version'],2)
            if row['stratum']=='multi-source-agreement':
                self.assertEqual(row['expected']['source_id'],min(f['source_id'] for f in row['evidence']))
            if row['stratum'] in ('conflict','unit-mismatch'):self.assertEqual(row['expected_behavior'],'abstain')

    def test_independent_ground_truth_from_current_exact_unit_records(self):
        rows=self.bank.development(self.generator)+self.bank.holdout(self.gate)
        entities=set()
        for row in rows:
            entity=re.fullmatch(r"What is sample (N[0-9a-f]{16})'s mass in mg\?",row['query']).group(1)
            self.assertNotIn(entity,entities);entities.add(entity)
            matches=[]
            for fact in row['evidence']:
                self.assertLessEqual(len(fact['source_id']),22)
                parsed=re.fullmatch(r'Sample (\w+) has (\w+) ([0-9]+\.[0-9]) (\w+)\.',fact['content'])
                name,measurement,value,unit=parsed.groups()
                if fact['current'] and (name,measurement,unit)==(entity,'mass','mg'):
                    matches.append((value,fact['source_id']))
            if not matches or len({value for value,_ in matches})!=1:
                expected=dict(status='abstain',entity='',measurement='',value='',unit='',source_id='')
            else:
                expected=dict(status='answer',entity=entity,measurement='mass',value=matches[0][0],unit='mg',
                              source_id=min(source for _,source in matches))
            self.assertEqual(row['expected'],expected)

    def test_same_seed_byte_reproducible_changed_seed_disjoint(self):
        other=self.root/'other';result=s.build(other,host_seed='a'*64)
        self.assertEqual(result['manifest_sha256'],self.result['manifest_sha256'])
        for name in ('dev.json','holdout.json','manifest.json'):
            self.assertEqual((self.directory/name).read_bytes(),(other/name).read_bytes())
        changed=self.root/'changed';s.build(changed,host_seed='b'*64)
        self.assertNotEqual((changed/'dev.json').read_bytes(),(other/'dev.json').read_bytes())
        self.assertNotIn('a'*64,(self.directory/'manifest.json').read_text())

    def test_exclusive_private_files_no_overwrite(self):
        before=(self.directory/'manifest.json').read_bytes()
        with self.assertRaises(FileExistsError):s.build(self.directory,host_seed='a'*64)
        self.assertEqual(before,(self.directory/'manifest.json').read_bytes())
        self.assertEqual(self.directory.stat().st_mode&0o777,0o700)
        for path in self.directory.iterdir():self.assertEqual(path.stat().st_mode&0o777,0o600)

    def test_forged_foreign_revoked_and_generator_denied_holdout(self):
        for actor in (self.generator,replace(self.gate),MemoryAuthority().issue('research','selection-gate',permissions=('read','approve')),
                      self.auth.issue('research','other-gate',permissions=('read','approve'))):
            with self.assertRaises(PermissionError):self.bank.holdout(actor)
        foreign=self.auth.issue('other','generator',permissions=('read',))
        with self.assertRaises(PermissionError):self.bank.development(foreign)
        self.auth.revoke(self.gate)
        with self.assertRaises(PermissionError):self.bank.holdout(self.gate)

    def test_gate_cannot_be_generator_or_proposer(self):
        for actor in (self.auth.issue('research','generator',permissions=('read','approve')),
                      self.auth.issue('research','gate',permissions=('read','approve','propose'))):
            with self.assertRaises(PermissionError):
                s.ScientificTaskBank(self.directory,self.auth,expected_manifest_hash=self.result['manifest_sha256'],
                    tenant_id='research',generator_agent_id='generator',gate_actor=actor)

    def test_disabled_and_missing_manifest_no_data(self):
        self.bank.enabled=False
        self.assertEqual(self.bank.status()['status'],'off')
        with self.assertRaisesRegex(ValueError,'off_disabled'):self.bank.development(self.generator)
        self.bank.enabled=True;self.bank.root=self.root/'missing'
        self.assertEqual(self.bank.status()['reason'],'no_data')
        with self.assertRaisesRegex(ValueError,'off_no_data'):self.bank.holdout(self.gate)

    def test_mutation_degraded_no_repair(self):
        path=self.directory/'dev.json';path.write_bytes(path.read_bytes()+b' ')
        changed=path.read_bytes()
        self.assertEqual(self.bank.status()['status'],'degraded')
        with self.assertRaisesRegex(ValueError,'degraded'):self.bank.development(self.generator)
        self.assertEqual(path.read_bytes(),changed)

    def test_manifest_mutation_external_pin_and_file_permissions(self):
        manifest=self.directory/'manifest.json';original=manifest.read_bytes()
        manifest.write_bytes(original+b' ')
        self.assertEqual(self.bank.status()['status'],'degraded')
        manifest.write_bytes(original);os.chmod(self.directory/'holdout.json',0o644)
        self.assertEqual(self.bank.status()['status'],'degraded')
        with self.assertRaises(ValueError):self.bank.holdout(self.gate)

    def test_seed_and_external_pin_validation(self):
        for seed in (None,'',True,'publicseed'):
            with self.assertRaises(ValueError):s.build(self.root/'bad',host_seed=seed)
        with self.assertRaises(ValueError):s.ScientificTaskBank(self.directory,self.auth,expected_manifest_hash='',tenant_id='research',generator_agent_id='generator')


if __name__=='__main__':unittest.main()
