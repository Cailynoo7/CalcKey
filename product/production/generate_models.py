"""Derive one STL per printed part from an exact Workbench handoff STEP.

Run with the CAD runtime Python. This imports the committed STEP, never replays
CAD cells, changes no CAD geometry and never slices or contacts a printer.
"""
from pathlib import Path
import argparse,csv,hashlib,json,struct
from collections import Counter
from build123d import import_step,export_stl,Location,Rot,Pos

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def validate_stl(p):
 b=p.read_bytes();n=struct.unpack_from('<I',b,80)[0]
 assert len(b)==84+50*n and n>0
 edges=Counter();degenerate=0
 for i in range(n):
  a=struct.unpack_from('<12fH',b,84+50*i)
  v=[tuple(round(x,5) for x in a[j:j+3]) for j in (3,6,9)]
  if len(set(v))<3:degenerate+=1;continue
  for j in range(3):edges[tuple(sorted((v[j],v[(j+1)%3])))]+=1
 return {'triangles':n,'collapsed_triangles_at_1e5mm':degenerate,
         'non_two_incidence_edges_at_1e5mm':sum(v!=2 for v in edges.values())}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('receipt');args=ap.parse_args()
 receipt_path=(ROOT/args.receipt).resolve();r=json.loads(receipt_path.read_text())
 assert r['designId']=='enclosure'
 a=next(a for a in r['artifacts'] if a['role']=='model/step');step=ROOT/a['path']
 assert sha(step)==a['sha256'] and step.stat().st_size==a['sizeBytes']
 design=json.loads((ROOT/'design/enclosure/source/design.json').read_text())
 for t in design['targets']:
  for c in t['cells']:
   key=t['id']+'/'+c['id']
   assert sha(ROOT/c['path'])==r['sourceHashes'][key],key
 transforms={o['id']:o['transform'] for o in design['objects']}
 assembly=import_step(step);objects={c.label:c for c in assembly.children}
 printed=['base','top','rear_foot_left','rear_foot_right','hinge_axle_left',
          'hinge_axle_right','hinge_cap_left','hinge_cap_right']
 printed += ['key_%02d'%i for i in range(1,21)]
 assert len(printed)==28 and len(set(printed))==28
 models=OUT/'models';models.mkdir(parents=True,exist_ok=True);rows=[]
 cache_path=ROOT/'.work/production-mesh-cache.json'
 cache_key=sha(Path(__file__))+'-'+a['sha256']+'-'+sha(ROOT/'design/enclosure/source/design.json')
 cache=json.loads(cache_path.read_text()) if cache_path.exists() else {}
 if cache.get('key')!=cache_key:cache={'key':cache_key,'entries':{}}
 for name in printed:
  obj=objects[name];t=transforms[name]
  local=Location(tuple(t['positionMm']),tuple(t['rotationDeg'])).inverse()*obj
  if name.startswith('key_') or name=='top':rotation=(180,0,0)
  elif name.startswith('hinge_axle_'):rotation=(0,-90,0)
  elif name.startswith('hinge_cap_') or name.startswith('rear_foot_'):rotation=(0,90,0)
  else:rotation=(0,0,0)
  part=Rot(*rotation)*local;bb=part.bounding_box()
  part=Pos(-(bb.min.X+bb.max.X)/2,-(bb.min.Y+bb.max.Y)/2,-bb.min.Z)*part
  assert part.is_valid and len(part.solids())==1,name
  if name.startswith('key_'):
   assert all(abs(v-target)<1e-4 for v,target in zip(part.bounding_box().size,(18.2,18.2,7)))
  dest=models/(name+'.stl')
  cached=cache['entries'].get(name)
  if cached and dest.exists() and sha(dest)==cached['sha256']:
   rows.append(cached);print(name,'verified existing mesh',flush=True);continue
  # OCCT can reject one tessellation density on an otherwise valid STEP solid.
  # Retry controlled densities, recording the successful value per object.
  attempts=[]
  for tolerance in (0.01,0.02,0.05):
   dest.unlink(missing_ok=True)
   ok=export_stl(part,dest,tolerance=tolerance,angular_tolerance=0.05)
   attempts.append({'tolerance_mm':tolerance,'writer_return':bool(ok)})
   if ok and dest.exists():
    checks=validate_stl(dest)
    if checks['non_two_incidence_edges_at_1e5mm']==0:break
  else:raise RuntimeError((name,'No closed STL from exact STEP',attempts))
  # Exact solid validity is checked above. Preserve mesh diagnostics for review.
  assert checks['non_two_incidence_edges_at_1e5mm']==0,(name,checks)
  row={'object_id':name,'file':str(dest.relative_to(ROOT)),'quantity':1,
       'material':'PLA' if name in ['base','top'] else 'PETG',
       'nozzle_mm':0.2 if name.startswith('key_') else 0.4,
       'layer_mm':0.1 if name.startswith('key_') else 0.15,
       'local_print_rotation_deg':list(rotation),'units':'mm','scale_percent':100,
       'bbox_mm':list(part.bounding_box().size),'min_z_mm':part.bounding_box().min.Z,
       'tolerance_mm':tolerance,'tessellation_attempts':attempts,
       'volume_mm3':part.volume,'bytes':dest.stat().st_size,'sha256':sha(dest),**checks}
  rows.append(row);print(name,'triangles',checks['triangles'],flush=True)
  cache['entries'][name]=row
  cache_path.parent.mkdir(parents=True,exist_ok=True)
  cache_path.write_text(json.dumps(cache,indent=2)+'\n')
 manifest={'source_receipt':str(receipt_path.relative_to(ROOT)),'revision':r['revision'],
           'export_id':r['exportId'],'source_step_sha256':a['sha256'],
           'conversion_only':True,'tolerance_mm_by_object':True,'angular_tolerance_rad':0.05,
           'units':'mm','printed_objects':28,'meshes':rows,
           'printer_started':False,'sliced':False}
 (OUT/'model-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 with (OUT/'print-plan.csv').open('w',encoding='utf-8-sig',newline='') as f:
  fields=['object_id','file','quantity','material','nozzle_mm','layer_mm','units','scale_percent']
  w=csv.DictWriter(f,fields,extrasaction='ignore',lineterminator='\n');w.writeheader();w.writerows(rows)
 print('28 STL meshes derived from the committed STEP; no slicing or printer action.')
if __name__=='__main__':main()
