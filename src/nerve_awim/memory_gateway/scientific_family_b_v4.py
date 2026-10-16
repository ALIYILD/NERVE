"""Registered v4: restrict source enum to query-relevant current measurements."""
from nerve_awim.memory_gateway import scientific_family_b_adapter as adapter


def prepare(query, evidence):
    prepared = adapter.prepare(query, evidence, 'adapted_v1')
    if prepared['route'] == 'model':
        entity = adapter.QUERY.fullmatch(query).group(1)
        prepared['schema']['properties']['source_id']['enum'] = [
            record['source_id'] for record in prepared['records']
            if record['current'] and
            (record['entity'], record['measurement'], record['unit']) ==
            (entity, 'mass', 'mg')
        ]
    return prepared
