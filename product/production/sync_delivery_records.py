"""Bind case STL updates to an identical handoff STEP, retaining historical measurements.

Only updates delivery records, buying notes and blank-document provenance.
No CAD replay, electrical tests, compilation, printing or device contact.
"""
import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from verify_mesh_features import verify as verify_keycaps
from verify_case_meshes import verify as verify_cases
from export_compatibility import same_shape, same_step, same_revision, verify_chain

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
BASELINE = 'product/production/history/before-harness-cad-receipt.json'
TESSELLATION = 'product/production/history/harness-tessellation-cad-receipt.json'


def read(p):
    return json.loads((ROOT / p).read_text(encoding='utf-8'))


def write(p, d):
    (ROOT / p).write_text(json.dumps(d, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def sha(p):
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def main(receipt_path):
    assert verify_chain()
    receipt = read(receipt_path)
    models = read('product/production/model-manifest.json')
    baseline, converted = read(BASELINE), read(TESSELLATION)
    step = next(a for a in receipt['artifacts'] if a['role'] == 'model/step')
    origin_step = next(a for a in converted['artifacts'] if a['role'] == 'model/step')
    assert sha(step['path']) == step['sha256']
    assert same_step(step['sha256'], origin_step['sha256'])
    assert same_revision(receipt['revision'], converted['revision'])
    assert same_revision(models['revision'], converted['revision'])
    assert receipt['shapeHashes'].keys() == converted['shapeHashes'].keys()
    assert all(same_shape(v, converted['shapeHashes'][n], n) for n, v in receipt['shapeHashes'].items())
    design = read('design/enclosure/source/design.json')
    placements = {o['id']: o['transform'] for o in design['objects']}
    for row in models['meshes']:
        n = row['object_id']
        assert row['sha256'] == sha(row['file'])
        assert same_shape(row['shape_sha256'], receipt['shapeHashes'][n], n)
        row['shape_sha256'] = receipt['shapeHashes'][n]
        assert row['object_transform'] == placements[n]
        if n in {'base', 'top'}:
            assert row['derivation']['method'] == 'step_tessellation'
            assert same_step(row['derivation']['step_sha256'], step['sha256'])
            row['derivation']['receipt'] = TESSELLATION
            row['derivation']['binding_note'] = 'Original tessellation preserved. Export-refresh and explicit seat-fix comparisons prove compatibility with the current source-only repair; no mesh regenerated in this update.'
        else:
            assert row['derivation']['method'] == 'reuse_unchanged_shape'
            assert same_shape(receipt['shapeHashes'][n], baseline['shapeHashes'][n], n)
    binding = {'receipt': receipt_path, 'revision': receipt['revision'],
               'export_id': receipt['exportId'], 'step_sha256': step['sha256'],
               'method': 'All 28 original meshes retained by byte hash, placement and verified export/seat-fix geometry equivalence; no retessellation in this package update',
               'tessellation_receipt': TESSELLATION,
               'source_compatibility_evidence': 'product/cad-compatibility/verification.json'}
    models.update(source_receipt=receipt_path, revision=receipt['revision'], export_id=receipt['exportId'],
                  source_step_sha256=step['sha256'], current_binding=binding)
    write('product/production/model-manifest.json', models)
    feature, case = verify_keycaps(), verify_cases()
    write('product/production/mesh-feature-checks.json', feature)
    write('product/production/case-mesh-checks.json', case)

    harness = read('product/harness-routing-verification.json')
    assert same_revision(harness['revision'], receipt['revision'])
    # Original geometric inspection export is evidence, not a new measurement.
    assert harness['export_id'] == converted['exportId']
    harness['export_receipt'] = TESSELLATION
    harness['current_handoff_binding'] = {**binding, 'all_shapes_equivalent_to_inspection_export': True,
        'measurement_revision': harness['revision'],
        'export_refresh_evidence': 'product/production/export-refresh-verification.json'}
    harness['limitations'] = [s for s in harness['limitations'] if not s.startswith('Old top/base STL')]
    harness['case_stl_feature_record'] = 'product/production/case-mesh-checks.json'
    write('product/harness-routing-verification.json', harness)

    keycaps = read('product/keycap-usability-verification.json')
    assert keycaps['revision'] == baseline['revision']
    assert keycaps['export_id'] == baseline['exportId']
    keycaps['export_receipt'] = BASELINE
    # Preserve the original motion-check revision/export; bind compatibility separately.
    keycaps['case_check_compatibility_binding'] = binding
    keycaps['current_assembly_binding'] = {**binding, 'measurement_revision': keycaps['revision'],
                                         'baseline_receipt': BASELINE, 'all_20_keycap_shapes_unchanged': True}
    write('product/keycap-usability-verification.json', keycaps)
    pcb = read('product/matrix-pcb-verification.json')
    assert same_revision(pcb['current_assembly_binding']['cad_revision'], receipt['revision'])
    pcb['current_assembly_binding'].update(cad_revision=receipt['revision'],
        cad_export_id=receipt['exportId'], receipt=receipt_path,
        source_compatibility_evidence='product/cad-compatibility/verification.json')
    write('product/matrix-pcb-verification.json', pcb)
    limits = list(dict.fromkeys(keycaps['limitations'] + pcb['limitations'] + harness['limitations']))
    write('product/production/design-verification.json', {
        'date': '2026-11-06', 'design_id': 'enclosure', 'revision': receipt['revision'],
        'export_id': receipt['exportId'], 'source_receipt': receipt_path, 'pcb_release_id': pcb['pcb_release_id'],
        'printed_parts': 28, 'mesh_binding': 'product/production/model-manifest.json',
        'geometry_checks': {
            'retained_keycap_measurements': {'path': 'product/keycap-usability-verification.json',
                                           'revision': keycaps['revision'], 'binding': keycaps['current_assembly_binding']},
            'current_case_and_harness': {'path': 'product/harness-routing-verification.json', 'revision': harness['revision']},
            'actual_stl_keycap_features': {'path': 'product/production/mesh-feature-checks.json', 'checks': feature['checks']},
            'actual_stl_case_features': {'path': 'product/production/case-mesh-checks.json', 'changed_meshes': case['changed_meshes']},
            'retained_pcb_assembly': {'path': 'product/matrix-pcb-verification.json', 'binding': pcb['current_assembly_binding']},
            'source_compatibility': 'product/cad-compatibility/verification.json',
            'regenerated_case_meshes': 0, 'unchanged_meshes': 28},
        'assembly_template': {'path': 'product/final-assembly/unpowered-checklist.csv', 'rows': 154, 'physical_results': 'pending'},
        'limitations': limits, 'physical_print_trial_skipped_by_user': True,
        'device_actions': {'printing_started': False, 'flashed': False, 'powered': False}})

    p = 'product/purchasing/matrix/hand-assembly-shopping.json'
    shopping = read(p)
    shopping.update(source_bom_sha256=sha('product/bom.json'), source_requirements_sha256=sha('product/requirements.json'),
                    enclosure_cad_revision=receipt['revision'], enclosure_export_id=receipt['exportId'])
    for row in shopping['items']:
        if row['bom_item_ids'] in {'enclosure_base', 'enclosure_top'}:
            row['category'] = '打印件'
            row['notes'] = '使用含五处固定桥的STEP及原主壳/底盖STL，mm、100%；本次仅修复CAD源码接口，全部28件网格经几何与哈希核对复用，按打印准备说明设置局部支撑，不另做试片。'
    write(p, shopping)
    path = ROOT / 'product/purchasing/matrix/hand-assembly-shopping.csv'
    with path.open(encoding='utf-8-sig', newline='') as f:
        fields = csv.DictReader(f).fieldnames
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(shopping['items'])
    p = 'product/purchasing/matrix/procurement-record.json'
    procurement = read(p)
    for key in ('printed_parts_unchanged', 'updated_keycap_meshes'):
        procurement['checks'].pop(key, None)
    procurement['checks'].update(regenerated_case_meshes=0, unchanged_printed_meshes=28,
                                 retained_keycap_meshes=20, printed_parts_total=28)
    procurement['harness_addendum'].pop('printed_meshes_to_refresh', None)
    procurement['harness_addendum'].update(regenerated_meshes=[], source_bom_sha256=sha('product/bom.json'),
                                          enclosure_export_id=receipt['exportId'], assembly_record_rows=154)
    for row in procurement['files']:
        row['sha256'] = sha('product/purchasing/matrix/' + row['name'])
    write(p, procurement)

    p = 'product/production/harness-delivery-addendum.json'
    addendum = read(p)
    addendum.pop('mesh_and_zip', None)
    addendum.update(cad_export={'revision': receipt['revision'], 'export_id': receipt['exportId'],
                               'receipt': receipt_path, 'step_sha256': step['sha256']},
                    mesh_delivery={'manifest': 'product/production/model-manifest.json',
                                   'new_case_meshes': [], 'unchanged_printed_meshes': 28,
                                   'compatibility_record': 'product/cad-compatibility/verification.json',
                                   'original_tessellation_receipt': TESSELLATION},
                    assembly_delivery={'guide': 'product/final-assembly/README.md',
                                       'blank_record': 'product/final-assembly/unpowered-checklist.csv', 'rows': 154},
                    complete_package_manifest='product/production/package-manifest.json')
    write(p, addendum)
    path = ROOT / 'product/final-assembly/README.md'
    text = path.read_text(encoding='utf-8')
    text = re.sub(r'export-[a-f0-9]{32}', receipt['exportId'], text)
    text = re.sub(r'(?<=几何revision `)[a-f0-9]{64}', receipt['revision'], text)
    path.write_text(text, encoding='utf-8')
    subprocess.run([sys.executable, str(ROOT/'product/final-assembly/generate.py')], check=True)
    print('PASS repaired-source delivery binding: 28 retained meshes, preserved inspection revisions, 154 pending records and purchasing hashes.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('receipt')
    main(parser.parse_args().receipt)
