"""Bind unchanged printed meshes to a new handoff using exact shape identity.

Does not build geometry, alter meshes, flash or contact devices. Original mesh
conversion records remain under history; current CAD/PCB evidence is separate.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent

def read(p): return json.loads((ROOT/p).read_text())
def sha(p): return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
def write(p,d): (ROOT/p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('receipt')
    args=ap.parse_args()
    proof=read('product/production/mesh-reuse-evidence.json')
    old=read(proof['original_receipt_copy'])
    assert sha(proof['original_receipt_copy'])==proof['original_receipt_sha256']
    models=read(proof['original_mesh_manifest'])
    assert sha(proof['original_mesh_manifest'])==proof['original_mesh_manifest_sha256']
    current=read(args.receipt)
    design=read('design/enclosure/source/design.json')
    transforms={o['id']:o['transform'] for o in design['objects']}
    names={m['object_id'] for m in models['meshes']}
    assert len(names)==28
    rows=[]
    for m in models['meshes']:
        n=m['object_id']
        assert old['shapeHashes'][n]==current['shapeHashes'][n],n+' geometry changed; regenerate STL'
        assert transforms[n]==proof['original_printed_transforms'][n],n+' placement changed'
        assert sha(m['file'])==m['sha256'],n+' mesh changed'
        rows.append({'object_id':n,'old_shape_sha256':old['shapeHashes'][n],
                     'current_shape_sha256':current['shapeHashes'][n],
                     'mesh_sha256':m['sha256']})
    step=next(a for a in current['artifacts'] if a['role']=='model/step')
    assert sha(step['path'])==step['sha256']
    models['source_receipt']=proof['original_receipt_copy']
    models['current_binding']={'receipt':args.receipt,'revision':current['revision'],
        'export_id':current['exportId'],'step_sha256':step['sha256'],
        'method':'unchanged Workbench shape hashes and identical printed-object transforms',
        'mesh_reuse_evidence':'product/production/mesh-reuse-evidence.json'}
    models['reuse_checks']=rows
    write('product/production/model-manifest.json',models)
    pcb=read('product/matrix-pcb-verification.json')
    assert pcb['cad_revision']==current['revision']
    baseline=read(proof['original_geometry_record'])
    record={'date':'2026-11-06','design_id':'enclosure','revision':current['revision'],
        'export_id':current['exportId'],'pcb_release_id':pcb['pcb_release_id'],
        'printed_parts':28,'mesh_binding':'product/production/model-manifest.json',
        'geometry_checks':{
            'current_matrix_assembly':{'path':'product/matrix-pcb-verification.json',
                'revision':pcb['cad_revision'],'scope':'matrix clearance, LCD budget, cap-to-switch alignment and external-stroke check, bottom removal'},
            'unchanged_printed_shapes':{'parts':rows,'scope':'exact exported shape hash and placement identity, not new physical measurements'},
            'earlier_geometry_checks':{'path':proof['original_geometry_record'],
                'revision':baseline['revision'],
                'scope':'retained earlier cap, foot, lens and storage-budget checks; revision preserved; used with unchanged-shape evidence'}},
        'limitations':list(dict.fromkeys(pcb['limitations']+baseline['limitations'])),
        'physical_print_trial_skipped_by_user':True,
        'device_actions':{'printing_started':False,'flashed':False,'powered':False}}
    write('product/production/design-verification.json',record)
    print('PASS: 28 unchanged shape hashes, placements and mesh hashes bound to current handoff.')
    print('Original conversion and geometry-check revisions preserved; no device actions.')

if __name__=='__main__':main()
