"""Read-only checks for the 30-part printing advice bundled with the handoff."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def verify(receipt):
    guide = ROOT/'product/print-preparation'
    checks = json.loads((guide/'source-checks.json').read_text())
    binding = checks['current_cad_binding']
    assert binding['revision'] == receipt['revision']
    assert binding['export_id'] == receipt['exportId']
    assert binding['step_sha256'] == receipt['artifacts'][0]['sha256']
    for key in ('input_sha256', 'mesh_sha256', 'document_sha256'):
        for path, expected in checks[key].items():
            assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == expected, path
    models = json.loads((ROOT/'product/production/model-manifest.json').read_text())
    model_rows = {r['object_id']: r for r in models['meshes']}
    with (guide/'part-settings.csv').open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == len(model_rows) == 30
    assert {r['object_id'] for r in rows} == model_rows.keys()
    assert sum(r['material'] == 'PLA' for r in rows) == 4
    assert sum(r['material'] == 'PETG' for r in rows) == 26
    for row in rows:
        m = model_rows[row['object_id']]
        assert int(row['quantity']) == m['quantity'] == 1
        assert row['material'] == m['material']
        assert float(row['nozzle_mm']) == m['nozzle_mm']
        assert float(row['layer_mm']) == m['layer_mm']
        assert json.loads(row['applied_rotation_deg_xyz']) == m['local_print_rotation_deg']
        assert row['stl_sha256'] == m['sha256'] and row['stl'] == m['file']
    return len(rows)


if __name__ == '__main__':
    model = json.loads((ROOT/'product/production/model-manifest.json').read_text())
    receipt = json.loads((ROOT/model['current_binding']['receipt']).read_text())
    print('PASS printing preparation:', verify(receipt), 'parts; versions, settings and input hashes match.')
