"""Verify existing published STEP files; never replay CAD source or change geometry."""
import gc
import hashlib
import json
import sys
from pathlib import Path
from build123d import import_step

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'product/production'))
from verify_export_refresh import blocks

NEW_RECEIPT = 'manufacturing/enclosure/releases/export-e9d67ce8536f1f9b0574ccf294968294/receipt.json'
NEEDED = {'rear_foot_left', 'rear_foot_right', 'hinge_cap_left', 'hinge_cap_right', 'screws'}


def read(path):
    return json.loads((ROOT/path).read_text())


def sha(path):
    return hashlib.sha256((ROOT/path).read_bytes()).hexdigest()


def residual_volume(result):
    # Solid.cut returns a ShapeList in build123d 0.10; compounds return shapes.
    return result.volume if hasattr(result, 'volume') else sum(s.volume for s in result)


def selected(path):
    print('Reading published STEP:', path, flush=True)
    assembly = import_step(ROOT/path)
    result = {}
    for child in list(assembly.children):
        if child.label in NEEDED:
            child.parent = None
            result[child.label] = child
    del child, assembly
    gc.collect()
    assert result.keys() == NEEDED
    return result


def main():
    old = read('product/cad-compatibility/before-seat-fix-receipt.json')
    new = read(NEW_RECEIPT)
    old_step = 'product/cad-compatibility/before-seat-fix.step'
    new_step = new['artifacts'][0]['path']
    assert sha(old_step) == old['artifacts'][0]['sha256']
    assert sha(new_step) == new['artifacts'][0]['sha256']
    assert old['assetHashes'] == new['assetHashes']
    source_changes = [n for n in old['sourceHashes'] if old['sourceHashes'][n] != new['sourceHashes'][n]]
    assert source_changes == ['base/base']
    old_design = read('product/cad-compatibility/before-seat-fix-design.json')
    new_design = read('design/enclosure/source/design.json')
    assert old_design['parameters'] == new_design['parameters']
    assert {o['id']: o['transform'] for o in old_design['objects']} == {o['id']: o['transform'] for o in new_design['objects']}
    before = read('product/cad-compatibility/before-seat-fix-facts.json')
    after = read('product/cad-compatibility/after-seat-fix-facts.json')
    assert before == after and len(after) == 32
    domain = read('product/cad-compatibility/domain-compare.json')
    assert domain['before_revision'] == old['revision'] and domain['after_revision'] == new['revision']
    matrix_report = next(r for r in domain['report']['topologyChanges'] if r['objectId'] == 'matrix_pcb')
    assert not any(matrix_report[k] for k in ('topologyChanged', 'geometryChanged', 'bboxChanged'))
    assert not any(matrix_report['countDelta'].values())
    a, b = blocks(ROOT/old_step), blocks(ROOT/new_step)
    assert a.keys() == b.keys()
    equal = sorted(n for n in a if n != 'enclosure' and a[n] == b[n])
    different = {n for n in a if a[n] != b[n]}
    assert different == NEEDED | {'matrix_pcb'}
    left, right = selected(old_step), selected(new_step)
    residuals = {}
    for name in sorted(NEEDED):
        if name == 'screws':
            key = lambda s: tuple(round(v, 5) for v in s.center())
            pairs = list(zip(sorted(left[name].solids(), key=key), sorted(right[name].solids(), key=key)))
            assert len(pairs) == len(left[name].solids()) == len(right[name].solids()) == 6
        else:
            pairs = [(left[name], right[name])]
        rows = []
        for previous, current in pairs:
            removed = residual_volume(previous.cut(current))
            added = residual_volume(current.cut(previous))
            assert abs(removed) < 1e-6 and abs(added) < 1e-6, (name, removed, added)
            rows.append({'removed_mm3': removed, 'added_mm3': added})
        residuals[name] = rows
        print('PASS exact two-way solid subtraction:', name, flush=True)
    # Matrix metadata differs, but its asset and transform are byte-identical;
    # the Workbench comparison independently reports geometryChanged=false.
    result = {'before_revision': old['revision'], 'after_revision': new['revision'],
              'before_receipt': 'product/cad-compatibility/before-seat-fix-receipt.json',
              'after_receipt': NEW_RECEIPT, 'before_step': old_step, 'after_step': new_step,
              'before_step_sha256': sha(old_step), 'after_step_sha256': sha(new_step),
              'source_cells_changed': source_changes, 'saved_parameters_identical': True,
              'placements_identical': True, 'numeric_geometry_identical_objects': 32,
              'normalized_step_geometry_blocks_identical': equal,
              'step_normalization': 'Object number namespaces, whitespace and assembly usage identifiers normalized; colour presentation references excluded.',
              'exact_boolean_difference_mm3': residuals, 'boolean_residual_tolerance_mm3': 1e-6,
              'matrix_reference_evidence': 'Same immutable STEP asset, import source cell and placement; domain compare geometryChanged=false, bboxChanged=false, topology counts unchanged.',
              'stl_regenerated': False, 'printed': False, 'powered': False, 'flashed': False}
    (HERE/'step-geometry-comparison.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS 28 printable solids, 6 screws, lens and Pico geometry; unchanged matrix asset/placement with domain comparison.', flush=True)


if __name__ == '__main__':
    main()
