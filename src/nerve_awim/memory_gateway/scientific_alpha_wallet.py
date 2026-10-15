"""Immutable per-bank alpha allocations, sealed before any simulated outcomes.

The ledger is created exclusively and never rewritten. Runtime claims/outcomes
belong to a separate authenticated journal. Trusted expected_sha256 must be
stored independently; a hash alone cannot authenticate a replacement ledger.
"""
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from .scientific_sequential_contract import canonical, number, register


class AlphaWallet:
    @staticmethod
    def create(path, registrations, *, total_alpha=.05):
        number(total_alpha, 1e-12, .05)
        entries, banks, identities, items = [], set(), set(), set()
        previous = ''
        for value in registrations:
            envelope = register(value)
            bank = value['bank']['manifest']; banks.add(bank)
            if len(banks) != 1: raise ValueError('one_bank_per_wallet')
            if value['study_id'] in identities: raise ValueError('duplicate_study')
            identities.add(value['study_id'])
            for item in value['schedule']:
                if item['item_id'] in items: raise ValueError('fresh_items_required_across_studies')
                items.add(item['item_id'])
            body = dict(study_id=value['study_id'], registration_sha256=envelope['sha256'],
                        alpha=value['gate']['alpha'], previous=previous)
            previous = sha256(canonical(body).encode()).hexdigest()
            entries.append(dict(body, sha256=previous))
        if not entries: raise ValueError('nonempty_wallet_required')
        if math.fsum(e['alpha'] for e in entries) > total_alpha + 1e-15:
            raise PermissionError('alpha_wallet_exhausted')
        ledger = dict(version='scientific-alpha-wallet-v1', bank=next(iter(banks)),
                      total_alpha=total_alpha, allocations=entries, head=previous)
        data = (canonical(ledger)+'\n').encode()
        path = Path(path)
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o400)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        return sha256(data).hexdigest()

    def __init__(self, path, *, expected_sha256):
        if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
            raise ValueError('independent_wallet_hash_required')
        self.path, self.expected_sha256 = Path(path), expected_sha256
        self.verify()

    def verify(self):
        if self.path.is_symlink(): raise ValueError('wallet_symlink')
        raw = self.path.read_bytes()
        if sha256(raw).hexdigest() != self.expected_sha256:
            raise ValueError('degraded — integrity: wallet hash mismatch')
        ledger = json.loads(raw)
        previous = ''; identities = set()
        for entry in ledger['allocations']:
            body = {k:v for k,v in entry.items() if k != 'sha256'}
            if body['previous'] != previous or sha256(canonical(body).encode()).hexdigest() != entry['sha256']:
                raise ValueError('degraded — integrity: wallet chain')
            if entry['study_id'] in identities: raise ValueError('duplicate_study')
            identities.add(entry['study_id']); previous = entry['sha256']
        if previous != ledger['head']: raise ValueError('degraded — integrity: wallet head')
        if math.fsum(e['alpha'] for e in ledger['allocations']) > ledger['total_alpha'] + 1e-15:
            raise PermissionError('alpha_wallet_exhausted')
        self.ledger = ledger
        return ledger

    def authorize(self, value):
        ledger = self.verify()
        envelope = register(value)
        matches = [e for e in ledger['allocations'] if e['study_id'] == value['study_id']]
        if not matches: raise PermissionError('alpha_wallet_exhausted_or_study_unallocated')
        if (value['bank']['manifest'] != ledger['bank'] or
                matches[0]['registration_sha256'] != envelope['sha256']):
            raise ValueError('registration_changed')
        return envelope
