"""Accept changed export hashes only through a measured STEP equivalence record."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from verify_export_refresh import blocks

ROOT = Path(__file__).resolve().parents[2]
ARCHIVES = {
    'manufacturing/enclosure/releases/export-6578a384546c9664928efcc137896bcd/receipt.json':
        'product/cad-compatibility/before-seat-fix-receipt.json',
    'manufacturing/enclosure/releases/export-6578a384546c9664928efcc137896bcd/model.step':
        'product/cad-compatibility/before-seat-fix.step',
}


def read(path):
    return json.loads((ROOT/ARCHIVES.get(path, path)).read_text())


def sha(path):
    return hashlib.sha256((ROOT/ARCHIVES.get(path, path)).read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def evidence():
    result = read('product/production/export-refresh-verification.json')
    old, new = [read(result[k]) for k in ('old_receipt', 'new_receipt')]
    assert old['revision'] == new['revision'] == result['revision']
    assert old['sourceHashes'] == new['sourceHashes'] and old['assetHashes'] == new['assetHashes']
    for k in ('old', 'new'):
        assert sha(result[k+'_step']) == result[k+'_step_sha256']
    assert result['results'].keys() == old['shapeHashes'].keys() == new['shapeHashes'].keys()
    for name, row in result['results'].items():
        assert row['old_shape_hash'] == old['shapeHashes'][name]
        assert row['new_shape_hash'] == new['shapeHashes'][name]
        assert row['source_assets_and_placement_identical']
        assert row['step_entity_blocks_identical'] or name == 'pico2'
        if name != 'pico2':
            assert row['old_entity_block_sha256'] == row['new_entity_block_sha256']
    return result


@lru_cache(maxsize=1)
def seat_evidence():
    record = read('product/cad-compatibility/verification.json')
    comparison = read(record['geometry_comparison'])
    old, new = [read(comparison[k+'_receipt']) for k in ('before', 'after')]
    for path, expected in record['input_sha256'].items():
        assert sha(path) == expected, path
    for path, expected in record['stl_files_unchanged'].items():
        assert sha(path) == expected, path
    assert old['revision'] == comparison['before_revision'] == record['before_revision']
    assert new['revision'] == comparison['after_revision'] == record['after_revision']
    assert old['assetHashes'] == new['assetHashes']
    assert [n for n in old['sourceHashes'] if old['sourceHashes'][n] != new['sourceHashes'][n]] == ['base/base']
    old_source = (ROOT/'product/cad-compatibility/before-seat-fix-base.py').read_text()
    new_source = (ROOT/'design/enclosure/source/parts/base/000-base.py').read_text()
    assert new_source.replace('# Explicit surface seats retain the legacy clearance-only holes and proud heads.\n', '').replace('seat="surface",', '') == old_source
    old_design = read('product/cad-compatibility/before-seat-fix-design.json')
    current = read('design/enclosure/source/design.json')
    assert old_design['parameters'] == current['parameters']
    assert {o['id']: o['transform'] for o in old_design['objects']} == {o['id']: o['transform'] for o in current['objects']}
    before = read('product/cad-compatibility/before-seat-fix-facts.json')
    after = read('product/cad-compatibility/after-seat-fix-facts.json')
    assert before == after and len(after) == 32
    assert len(comparison['normalized_step_geometry_blocks_identical']) == 26
    differences = comparison['exact_boolean_difference_mm3']
    assert set(differences) == {'hinge_cap_left', 'hinge_cap_right', 'rear_foot_left', 'rear_foot_right', 'screws'}
    assert len(differences['screws']) == 6 and all(len(rows) == 1 for n, rows in differences.items() if n != 'screws')
    assert all(abs(row[k]) < 1e-6 for rows in differences.values() for row in rows for k in ('added_mm3', 'removed_mm3'))
    matrix = next(r for r in read(record['domain_comparison'])['report']['topologyChanges'] if r['objectId'] == 'matrix_pcb')
    assert not any(matrix[k] for k in ('topologyChanged', 'geometryChanged', 'bboxChanged'))
    assert not any(matrix['countDelta'].values())
    for which, receipt in (('before', old), ('after', new)):
        assert sha(comparison[which+'_step']) == comparison[which+'_step_sha256'] == receipt['artifacts'][0]['sha256']
    return comparison, old, new


def verify_chain():
    runtime = evidence()
    a, b = [blocks(ROOT/ARCHIVES.get(runtime[k+'_step'], runtime[k+'_step'])) for k in ('old', 'new')]
    for name, row in runtime['results'].items():
        assert a[name] == row['old_entity_block_sha256'] and b[name] == row['new_entity_block_sha256']
    comparison, _, _ = seat_evidence()
    c = blocks(ROOT/comparison['after_step'])
    assert c.keys() == b.keys()
    identical = sorted(n for n in c if n != 'enclosure' and c[n] == b[n])
    assert identical == comparison['normalized_step_geometry_blocks_identical']
    return True


def connected(a, b, edges):
    reached = {a}
    for _ in edges:
        for x, y in edges:
            if x in reached or y in reached:
                reached.update((x, y))
    return b in reached


def same_shape(a, b, name):
    if a == b:
        return True
    row = evidence()['results'][name]
    _, before, after = seat_evidence()
    return connected(a, b, [(row['old_shape_hash'], row['new_shape_hash']),
                            (before['shapeHashes'][name], after['shapeHashes'][name])])


def same_step(a, b):
    if a == b:
        return True
    runtime = evidence()
    seat, _, _ = seat_evidence()
    return connected(a, b, [(runtime['old_step_sha256'], runtime['new_step_sha256']),
                            (seat['before_step_sha256'], seat['after_step_sha256'])])


def same_revision(a, b):
    if a == b:
        return True
    comparison, _, _ = seat_evidence()
    return {a, b} == {comparison['before_revision'], comparison['after_revision']}
