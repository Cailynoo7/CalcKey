"""Derive one STL per printed part from an exact Workbench handoff STEP.

Run with the CAD runtime Python. This imports the committed STEP, never replays
CAD cells, changes no CAD geometry and never slices or contacts a printer.
"""
from pathlib import Path
import argparse,csv,hashlib,json,struct,gc
from collections import Counter
from export_compatibility import same_shape
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
def remove_exact_zero_area(p):
 # OCCT can emit one repeated-vertex triangle at a spherical pole. Removing
 # exactly zero-area facets changes no surface and is followed by a full
 # edge-incidence check. Never weld, move or fill non-degenerate geometry.
 data=p.read_bytes();count=struct.unpack_from('<I',data,80)[0];kept=[]
 for i in range(count):
  raw=data[84+50*i:84+50*(i+1)];a=struct.unpack('<12fH',raw)
  vertices=[a[j:j+3] for j in (3,6,9)]
  if len(set(vertices))==3:kept.append(raw)
 removed=count-len(kept)
 if removed:p.write_bytes(data[:80]+struct.pack('<I',len(kept))+b''.join(kept))
 return removed
def main():
 ap=argparse.ArgumentParser();ap.add_argument('receipt')
 modes=ap.add_mutually_exclusive_group()
 modes.add_argument('--keycaps-only',action='store_true',help='Regenerate 20 caps; verify and reuse the historical 8 mechanisms')
 modes.add_argument('--typec-only',action='store_true',help='Tessellate base/top/two controller bridges; verify and reuse 26 other meshes')
 modes.add_argument('--case-only',action='store_true',help='Regenerate base/top; verify and reuse 26 meshes against the saved pre-harness export')
 args=ap.parse_args()
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
 baseline_path='product/production/history/before-typec-model-manifest.json' if args.typec_only else 'product/production/history/before-harness-model-manifest.json' if args.case_only else 'product/production/history/matrix-before-keycap-model-manifest.json'
 baseline_receipt='product/production/history/before-typec-cad-receipt.json' if args.typec_only else 'product/production/history/before-harness-cad-receipt.json' if args.case_only else None
 previous=json.loads((ROOT/baseline_path).read_text()) if args.keycaps_only or args.case_only or args.typec_only else None
 baseline_receipt=baseline_receipt or (previous['source_receipt'] if previous else None)
 prior_receipt=json.loads((ROOT/baseline_receipt).read_text()) if previous else None
 prior_transforms=({m['object_id']:m['object_transform'] for m in previous['meshes']} if args.case_only or args.typec_only else
                   json.loads((OUT/'mesh-reuse-evidence.json').read_text())['original_printed_transforms']) if previous else {}
 previous_rows={m['object_id']:m for m in previous['meshes']} if previous else {}
 printed=['base','top','rear_foot_left','rear_foot_right','hinge_axle_left',
          'hinge_axle_right','hinge_cap_left','hinge_cap_right']
 printed += ['key_%02d'%i for i in range(1,21)]
 if args.typec_only: printed += ['controller_clamp_a','controller_clamp_b']
 assert len(printed)==len(set(printed)) and len(printed)==(30 if args.typec_only else 28)
 regenerate={'base','top','controller_clamp_a','controller_clamp_b'} if args.typec_only else {n for n in printed if n in {'base','top'}} if args.case_only else {n for n in printed if n.startswith('key_')} if args.keycaps_only else set(printed)
 models=OUT/'models';models.mkdir(parents=True,exist_ok=True);rows=[]
 cache_path=ROOT/'.work/production-mesh-cache.json'
 cache_key=sha(Path(__file__))+'-'+a['sha256']+'-'+sha(ROOT/'design/enclosure/source/design.json')
 cache=json.loads(cache_path.read_text()) if cache_path.exists() else {}
 if cache.get('key')!=cache_key:
  retained={}
  for name,row in cache.get('entries',{}).items():
   path=ROOT/row['file']
   if (row.get('derivation',{}).get('step_sha256')==a['sha256']
       and row.get('shape_sha256')==r['shapeHashes'].get(name)
       and path.exists() and sha(path)==row['sha256']):
    checks=validate_stl(path)
    if checks['non_two_incidence_edges_at_1e5mm']==checks['collapsed_triangles_at_1e5mm']==0:retained[name]=row
  cache={'key':cache_key,'entries':retained}
 valid_cached={name for name,row in cache['entries'].items()
               if (ROOT/row['file']).exists() and sha(ROOT/row['file'])==row['sha256']}
 needed=regenerate-valid_cached
 objects={}
 if needed:
  assembly=import_step(step)
  for child in list(assembly.children):
   if child.label in needed:
    child.parent=None
    objects[child.label]=child
  # Do not retain the large PCB/vendor assembly or already-converted caps.
  del child,assembly
  gc.collect()
  assert objects.keys()==needed
 for name in printed:
  if name not in regenerate:
   old=previous_rows[name]
   assert same_shape(r['shapeHashes'][name],prior_receipt['shapeHashes'][name],name),name+' shape changed'
   assert transforms[name]==prior_transforms[name],name+' placement changed'
   assert sha(ROOT/old['file'])==old['sha256'],name+' mesh changed'
   checked=validate_stl(ROOT/old['file'])
   assert checked['non_two_incidence_edges_at_1e5mm']==checked['collapsed_triangles_at_1e5mm']==0
   row=dict(old,shape_sha256=r['shapeHashes'][name],object_transform=transforms[name],
            derivation={'method':'reuse_unchanged_shape','receipt':baseline_receipt,
                        'mesh_manifest':baseline_path,'source_mesh_sha256':old['sha256'],
                        'original_derivation':old['derivation']})
   rows.append(row);print(name,'unchanged shape, placement and mesh verified',flush=True);continue
  dest=models/(name+'.stl')
  cached=cache['entries'].get(name)
  if cached and dest.exists() and sha(dest)==cached['sha256']:
   rows.append(cached);print(name,'verified existing mesh',flush=True);continue
  obj=objects.pop(name);t=transforms[name]
  local=Location(tuple(t['positionMm']),tuple(t['rotationDeg'])).inverse()*obj
  if name.startswith('key_') or name=='top':rotation=(180,0,0)
  elif name.startswith('hinge_axle_'):rotation=(0,-90,0)
  elif name.startswith('hinge_cap_') or name.startswith('rear_foot_'):rotation=(0,90,0)
  else:rotation=(0,0,0)
  part=Rot(*rotation)*local;bb=part.bounding_box()
  print_translation=[-(bb.min.X+bb.max.X)/2,-(bb.min.Y+bb.max.Y)/2,-bb.min.Z]
  part=Pos(*print_translation)*part
  assert part.is_valid and len(part.solids())==1,name
  if name.startswith('key_'):
   assert all(abs(v-target)<1e-4 for v,target in zip(part.bounding_box().size,(18.2,18.2,7)))
  # OCCT can reject one tessellation density on an otherwise valid STEP solid.
  # Retry controlled densities, recording the successful value per object.
  attempts=[]
  for tolerance in (0.01,0.02,0.05):
   temporary=dest.with_name(name+'.tmp-export.stl')
   temporary.unlink(missing_ok=True)
   ok=export_stl(part,temporary,tolerance=tolerance,angular_tolerance=0.05)
   attempts.append({'tolerance_mm':tolerance,'writer_return':bool(ok)})
   if ok and temporary.exists():
    zero_area_removed=remove_exact_zero_area(temporary)
    checks=validate_stl(temporary)
    if checks['non_two_incidence_edges_at_1e5mm']==0 and checks['collapsed_triangles_at_1e5mm']==0:
     temporary.replace(dest);break
  else:raise RuntimeError((name,'No closed STL from exact STEP',attempts))
  # Exact solid validity is checked above. Preserve mesh diagnostics for review.
  assert checks['non_two_incidence_edges_at_1e5mm']==0,(name,checks)
  row={'object_id':name,'file':str(dest.relative_to(ROOT)),'quantity':1,
       'material':'PLA' if name in ['base','top','controller_clamp_a','controller_clamp_b'] else 'PETG',
       'nozzle_mm':0.2 if name.startswith('key_') else 0.4,
       'layer_mm':0.1 if name.startswith('key_') else 0.15,
       'local_print_rotation_deg':list(rotation),'units':'mm','scale_percent':100,
       'local_print_translation_mm':print_translation,
       'bbox_mm':list(part.bounding_box().size),'min_z_mm':part.bounding_box().min.Z,
       'tolerance_mm':tolerance,'tessellation_attempts':attempts,
       'exact_zero_area_facets_removed':zero_area_removed,
       'volume_mm3':part.volume,'bytes':dest.stat().st_size,'sha256':sha(dest),
       'shape_sha256':r['shapeHashes'][name],'object_transform':transforms[name],
       'derivation':{'method':'step_tessellation','receipt':str(receipt_path.relative_to(ROOT)),
                     'step_sha256':a['sha256']},**checks}
  rows.append(row);print(name,'triangles',checks['triangles'],flush=True)
  cache['entries'][name]=row
  cache_path.parent.mkdir(parents=True,exist_ok=True)
  cache_path.write_text(json.dumps(cache,indent=2)+'\n')
  del part,local,obj
  gc.collect()
 manifest={'source_receipt':str(receipt_path.relative_to(ROOT)),'revision':r['revision'],
           'export_id':r['exportId'],'source_step_sha256':a['sha256'],
           'conversion_only':True,'tolerance_mm_by_object':True,'angular_tolerance_rad':0.05,
           'units':'mm','printed_objects':len(printed),'meshes':rows,
           'printer_started':False,'sliced':False}
 manifest['current_binding']={'receipt':str(receipt_path.relative_to(ROOT)),'revision':r['revision'],
          'export_id':r['exportId'],'step_sha256':a['sha256'],
          'method':'Type-C base/top/two controller bridges tessellated; 26 unchanged meshes verified by exact shape, transform and bytes' if args.typec_only else 'base/top tessellated from current STEP; 26 unchanged meshes verified by shape, transform and bytes' if args.case_only else '20 caps tessellated from current STEP; 8 unchanged meshes verified by shape, transform and bytes' if args.keycaps_only else 'all parts tessellated from current STEP'}
 (OUT/'model-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 with (OUT/'print-plan.csv').open('w',encoding='utf-8-sig',newline='') as f:
  fields=['object_id','file','quantity','material','nozzle_mm','layer_mm','units','scale_percent']
  w=csv.DictWriter(f,fields,extrasaction='ignore',lineterminator='\n');w.writeheader();w.writerows(rows)
 print(str(len(printed))+' STL meshes bound to committed STEP; no slicing or printer action.')
if __name__=='__main__':main()
