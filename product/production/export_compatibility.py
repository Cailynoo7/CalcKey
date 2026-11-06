"""Accept changed export hashes only through a measured STEP equivalence record."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def evidence():
    result = json.loads((ROOT/'product/production/export-refresh-verification.json').read_text())
    old, new = [json.loads((ROOT/result[k]).read_text()) for k in ('old_receipt', 'new_receipt')]
    assert old['revision'] == new['revision'] == result['revision']
    assert old['sourceHashes'] == new['sourceHashes'] and old['assetHashes'] == new['assetHashes']
    for k in ('old', 'new'):
        assert hashlib.sha256((ROOT/result[k+'_step']).read_bytes()).hexdigest() == result[k+'_step_sha256']
    assert result['results'].keys() == old['shapeHashes'].keys() == new['shapeHashes'].keys()
    for name, row in result['results'].items():
        assert row['old_shape_hash'] == old['shapeHashes'][name]
        assert row['new_shape_hash'] == new['shapeHashes'][name]
        assert row['source_assets_and_placement_identical']
        assert row['step_entity_blocks_identical'] or name == 'pico2'
        if name != 'pico2':
            assert row['old_entity_block_sha256'] == row['new_entity_block_sha256']
    return result


def same_shape(a, b, name):
    if a == b:
        return True
    row = evidence()['results'][name]
    return {a, b} == {row['old_shape_hash'], row['new_shape_hash']}


def same_step(a, b):
    if a == b:
        return True
    record = evidence()
    return {a, b} == {record['old_step_sha256'], record['new_step_sha256']}
