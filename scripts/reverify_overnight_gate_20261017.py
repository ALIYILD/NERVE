"""Read-only replay of the existing failed gate grid; never runs new studies."""
import contextlib
import gzip
import hashlib
import io
import json
from pathlib import Path
import socket
from unittest.mock import patch

import audit_gate_v3_2_rare_promotions as audit
from nerve_awim.memory_gateway import retained_promotion_gate

ROOT = Path(__file__).resolve().parents[1]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def run():
    index = json.loads((ROOT / 'docs/galahad/evidence/gate-v3_2-grid-research-evidence-index.json').read_text())
    for name, expected in index['files'].items():
        assert digest((ROOT / name).read_bytes()) == expected, name
    result = audit.sim.read(audit.sim.OUT / 'result.json')
    total = 0
    for name, cell in result['results'].items():
        compressed = (ROOT / cell['receipt']['path']).read_bytes()
        assert digest(compressed) == cell['receipt']['sha256'], name
        raw = gzip.decompress(compressed)
        assert digest(raw) == cell['receipt']['raw_sha256'], name
        rows = json.loads(raw)
        assert len(rows) == cell['streams'], name
        assert sum(r['promoted'] for r in rows) == cell['accepted'], name
        assert sum(r['items'] for r in rows) == cell['total_items'], name
        assert max(r['items'] for r in rows) == cell['max_items'], name
        total += len(rows)
    captured = []
    with patch.object(audit.sim, 'write', lambda path, report: captured.append(report)), contextlib.redirect_stdout(io.StringIO()):
        audit.run()
    assert len(captured) == 1
    assert result['eligible_m'] == [] and result['chosen_m'] is None
    proof = retained_promotion_gate.verify()
    bank = Path(proof['payload']['bank_v4']['gate_private_directory'])
    ledger_path = bank / 'consumption-ledger.json'
    ledger = json.loads(ledger_path.read_text())
    return {
        'verdict': 'retain_incumbent',
        'canonical_gate': 'v3', 'canonical_signature_verified': proof['verified'],
        'payload_sha256': proof['payload_sha256'],
        'indexed_files_verified': len(index['files']),
        'receipt_cells_verified': len(result['results']), 'receipt_rows_verified': total,
        'aggregate_replay': 'counts, promotions, total and maximum items; not full scalar replay of all streams',
        'harmful_scalar_replay': captured[0],
        'eligible_m': [], 'chosen_m': None, 'signing_payload_prepared': False,
        'bank_v4': {'ledger_sha256': digest(ledger_path.read_bytes()),
                    'consumed_items': ledger['consumed_items'],
                    'allocations': [{'state': a['state'], 'consumed': a['consumed'],
                                     'registration_sha256': a['registration_sha256'],
                                     'reserved_slots': sum(map(len, a['slots'].values()))}
                                    for a in ledger['allocations']]},
        'model_calls': 0, 'pod_operations': 0, 'reserve_items_consumed': 0,
        'source_sha256': digest(Path(__file__).read_bytes()),
    }


if __name__ == '__main__':
    def deny(*args, **kwargs):
        raise RuntimeError('Replay is CPU-only; network forbidden')
    with patch.object(socket.socket, 'connect', deny), patch.object(socket.socket, 'connect_ex', deny), patch.object(socket, 'create_connection', deny):
        print(json.dumps(run(), sort_keys=True, indent=2))
