"""Check the delivered STL geometry, independently of CAD parameter names."""
import hashlib
import json
import struct
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent

def triangles(path):
    data=path.read_bytes()
    count=struct.unpack_from('<I',data,80)[0]
    assert len(data)==84+50*count
    result=[]
    for i in range(count):
        a=struct.unpack_from('<12fH',data,84+50*i)
        result.append([a[3:6],a[6:9],a[9:12]])
    return result

def first_z(tris,x,y):
    hits=[]
    for a,b,c in tris:
        d=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(d)<1e-12:continue
        u=((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/d
        v=((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/d
        w=1-u-v
        if min(u,v,w)>=-1e-7:hits.append(u*a[2]+v*b[2]+w*c[2])
    assert hits,(x,y,'no STL surface')
    return min(hits)

def verify():
    manifest=json.loads((OUT/'model-manifest.json').read_text())
    previous=json.loads((OUT/'history/matrix-before-keycap-model-manifest.json').read_text())
    old={m['object_id']:m for m in previous['meshes']}
    current={m['object_id']:m for m in manifest['meshes']}
    keys=['key_%02d'%i for i in range(1,21)]
    assert all(current[n]['sha256']!=old[n]['sha256'] for n in keys)
    assert all(current[n]['sha256']==old[n]['sha256'] for n in current if n not in keys)
    five=triangles(OUT/'models/key_10.stl')
    # STL is print-oriented with the cap top down: local (0,-4.6,7) -> (0,+4.6,0).
    center=first_z(five,0,4.6)
    beside=first_z(five,1.4,4.6)
    assert abs(center-0.35)<0.03 and abs(beside)<1e-4
    enter=triangles(OUT/'models/key_16.stl')
    floors=[t for t in enter if all(abs(v[2]-0.35)<1e-4 for v in t)]
    top=[v for t in floors for v in t if v[1]<0]
    bottom=[v for t in floors for v in t if v[1]>0]
    assert len(top)>0 and len(bottom)>0
    top_y=[min(v[1] for v in top),max(v[1] for v in top)]
    bottom_y=[min(v[1] for v in bottom),max(v[1] for v in bottom)]
    assert top_y[1]<-1 and bottom_y[0]>1
    assert 7<max(v[0] for v in top)-min(v[0] for v in top)<10
    assert 2<max(v[0] for v in bottom)-min(v[0] for v in bottom)<4
    paths=['product/production/models/key_10.stl','product/production/models/key_16.stl']
    return {'revision':manifest['revision'],'export_id':manifest['export_id'],
            'checks':{'new_keycap_meshes':20,'unchanged_other_meshes':8,
                      'five_recess_depth_from_stl_mm':center-beside,
                      'five_adjacent_top_z_mm':beside,
                      'enter_recess_y_range_print_frame_mm':top_y,
                      'equals_recess_y_range_print_frame_mm':bottom_y,
                      'legend_depth_mm':0.35},
            'mesh_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
            'physical_tests_performed':False}

if __name__=='__main__':
    report=verify()
    (OUT/'mesh-feature-checks.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS actual STL surfaces: 5 recess depth, separated Enter/= floors; 20 new caps, 8 unchanged meshes.')
