"""Verify and package the current Type-C handoff. Never build CAD or touch hardware."""
import argparse,csv,hashlib,json,struct,subprocess,sys,zipfile
from datetime import datetime,timezone
from pathlib import Path
from verify_case_meshes import verify as verify_cases,topology
from verify_mesh_features import verify as verify_features,triangles
from verify_print_preparation import verify as verify_printing
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
TARGET=ROOT/'product/calckey-complete-design.zip'

def read(p):return json.loads((ROOT/p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(ok,msg):
 if not ok:raise ValueError(msg)
def verify_hash(p,expected):require((ROOT/p).is_file() and sha(ROOT/p)==expected,'Missing/changed file: '+p)
def rows(p):
 with (ROOT/p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def canonical(v):
 if isinstance(v,float) and v.is_integer():return int(v)
 if isinstance(v,dict):return {k:canonical(x) for k,x in v.items()}
 if isinstance(v,list):return [canonical(x) for x in v]
 return v

def main(check_only=False):
 models=read('product/production/model-manifest.json');binding=models['current_binding'];receipt=read(binding['receipt']);step=next(x for x in receipt['artifacts'] if x['role']=='model/step')
 require(receipt['status']=='handoff' and receipt['revision']==binding['revision']==models['revision'],'CAD handoff revision mismatch')
 require(receipt['exportId']==binding['export_id']==models['export_id'],'CAD export mismatch');verify_hash(step['path'],step['sha256'])
 require(binding['step_sha256']==step['sha256'],'STEP binding mismatch')
 design=read('design/enclosure/source/design.json');require({o['id']:o['shapeHash'] for o in design['objects']}==receipt['shapeHashes'],'Current CAD object differs from published STEP')
 for target in design['targets']:
  for cell in target['cells']:verify_hash(cell['path'],receipt['sourceHashes'][target['id']+'/'+cell['id']])
 active_assets=set(receipt['assetHashes'].values())
 for h in active_assets:verify_hash('design/enclosure/source/assets/'+h+'.step',h)
 verify_hash(receipt['stateManifest']['brief']['path'],receipt['stateManifest']['brief']['sha256'])
 for entry in receipt['stateManifest']['requirement']['inputs']:verify_hash(entry['path'],entry['sha256'])
 require(all(receipt['interference']['counts'][k]==0 for k in ['undeclared','over_budget','undetermined']),'Unresolved CAD overlap')
 repair=read('product/type-c-reference-repair.json');verify_hash(repair['source'],repair['source_sha256']);verify_hash(repair['output'],repair['output_sha256'])
 require(receipt['assetHashes']['pico2']==repair['output_sha256'] and repair['unchanged_other_solids']==121 and repair['roundtrip_valid']==[True,True],'Controller repair binding mismatch')
 require(repair['source_minus_repaired_mm3']==repair['repaired_minus_source_mm3']==0,'Reference geometry difference')
 expected={'base','top','controller_clamp_a','controller_clamp_b','rear_foot_left','rear_foot_right','hinge_axle_left','hinge_axle_right','hinge_cap_left','hinge_cap_right'}|{'key_%02d'%i for i in range(1,21)}
 require(len(models['meshes'])==30 and {m['object_id'] for m in models['meshes']}==expected,'Printed inventory mismatch')
 transforms={o['id']:o['transform'] for o in design['objects']}
 for m in models['meshes']:
  n=m['object_id'];verify_hash(m['file'],m['sha256']);require(m['shape_sha256']==receipt['shapeHashes'][n] and m['object_transform']==transforms[n],'STL CAD binding mismatch '+n)
  require(m['units']=='mm' and m['scale_percent']==100 and abs(m['min_z_mm'])<1e-5,'STL scale/origin mismatch '+n)
  require((ROOT/m['file']).stat().st_size==m['bytes'],'STL size mismatch '+n)
  tris=triangles(ROOT/m['file']);t=topology(tris)
  volume=sum((a[0]*(b[1]*c[2]-b[2]*c[1])+a[1]*(b[2]*c[0]-b[0]*c[2])+a[2]*(b[0]*c[1]-b[1]*c[0]))/6 for a,b,c in tris)
  require(volume>0 and abs(volume-m['volume_mm3'])<max(0.2,m['volume_mm3']*.01),'STL volume/orientation mismatch '+n)
  require(abs(min(v[2] for tri in tris for v in tri))<1e-4,'Actual STL does not rest at Z=0 '+n)
  require(t['connected_surface_components']==1 and all(t[k]==0 for k in ['collapsed_triangles_at_1e5mm','non_two_incidence_edges_at_1e5mm','inconsistent_edge_orientations']),'STL topology failure '+n)
  d=m['derivation']
  if d['method']=='reuse_unchanged_shape':
   previous=read(d['receipt']);prior=next(x for x in read(d['mesh_manifest'])['meshes'] if x['object_id']==n)
   require(previous['shapeHashes'][n]==receipt['shapeHashes'][n] and prior['sha256']==m['sha256'] and prior['object_transform']==transforms[n],'Reused STL provenance mismatch '+n)
  else:require(d['method']=='step_tessellation' and d['step_sha256']==step['sha256'] and d['receipt']==binding['receipt'],'Converted STL not from current STEP '+n)
 require({p.stem for p in (OUT/'models').glob('*.stl')}==expected,'Unexpected mesh files')
 require(verify_features()==read('product/production/mesh-feature-checks.json'),'STL keycap feature record stale')
 require(verify_cases()==read('product/production/case-mesh-checks.json'),'STL case feature record stale')
 require(verify_printing(receipt)==30,'Printing advice inventory mismatch')
 require(len(rows('product/production/print-plan.csv'))==30,'Print plan inventory mismatch')
 bom=read('product/bom.json');items={i['id']:i for i in bom['items']};selection=read('product/component-selection.json')
 require(len(items)==31 and selection['selected_components']==bom['items'],'BOM/selection mismatch')
 values={k:v['value'] for k,v in read('product/requirements.json')['requirements'].items()};req_hash=hashlib.sha256(json.dumps(canonical(values),sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
 require(bom['requirements_digest']==req_hash,'BOM requirement digest stale')
 csv_bom={i['id']:i for i in rows('product/bom.csv')};require(csv_bom.keys()==items.keys(),'BOM CSV inventory mismatch')
 for k,i in items.items():require(csv_bom[k]['name']==i['name'] and csv_bom[k]['quantity']==str(i['quantity']),'BOM CSV mismatch '+k)
 require('RP2350-Plus-16MB' in items['controller']['name'] and items['signal_wire']['quantity']==10 and items['lcd_signal_wire']['quantity']==5,'Controller/wire variant mismatch')
 fwdir='design/firmware/release/v0.3.0';fw=read(fwdir+'/verification.json')
 require(fw['version']=='0.3.0' and fw['board']=='waveshare_rp2350_plus_16mb' and fw['flash_size_bytes']==16777216,'Firmware target mismatch')
 require(fw['host_test_counts']==[93,47270,2500,3023] and all(x['exit_code']==0 for x in fw['commands']),'Firmware compile/test record failed')
 require(not fw['flashed'] and not fw['hardware_tested'],'Physical firmware result incorrectly claimed')
 for p,h in fw['source_hashes'].items():verify_hash(p,h)
 for name,a in fw['artifacts'].items():verify_hash(fwdir+'/'+name,a['sha256']);require((ROOT/fwdir/name).stat().st_size==a['bytes'],'Firmware size mismatch')
 fwzip='product/calckey-firmware-v0.3.0.zip'
 with zipfile.ZipFile(ROOT/fwzip) as z:
  require(z.testzip() is None,'Firmware ZIP CRC failure')
  names=set(z.namelist());prefix='CalcKey-v0.3.0/'
  required={prefix+n for n in fw['artifacts']}|{prefix+'verification.json'}
  required|={prefix+'project/'+p for p in fw['source_hashes'] if p.startswith('design/firmware/') or p in ['design/enclosure/source/wiring.json','product/requirements.json']}
  require(required<=names,'Firmware ZIP omits required source or artifacts')
  for name in z.namelist():
   if name.endswith('/'):continue
   if '/project/' in name:p=name.split('/project/',1)[1]
   else:p=fwdir+'/'+name.rsplit('/',1)[-1]
   require((ROOT/p).is_file() and hashlib.sha256(z.read(name)).hexdigest()==sha(ROOT/p),'Firmware ZIP byte mismatch '+name)
 pcb_id=read('manufacturing/matrix/release-index.json')['releases'][-1]['releaseId'];pcb_dir='manufacturing/matrix/releases/'+pcb_id;pcb=read(pcb_dir+'/release-manifest.json')
 require(all(s['status']=='ready' for s in pcb['sections']),'PCB release blocked')
 for a in pcb['package']:verify_hash(pcb_dir+'/package/'+a['path'],a['sha256'])
 pcb_step=next(a for a in pcb['package'] if a['path']=='assembly.step');require(receipt['assetHashes']['matrix_pcb']==pcb_step['sha256'],'PCB/CAD imported STEP mismatch')
 order=read('product/purchasing/matrix/pcb-order-parameters.json');require(order['pcb_release_id']==pcb_id,'PCB ordering version mismatch')
 fabrication='product/production/matrix-fabrication.zip';verify_hash(fabrication,order['fabrication_package']['sha256'])
 fab_files=next(s['files'] for s in pcb['sections'] if s['id']=='fabrication')
 with zipfile.ZipFile(ROOT/fabrication) as z:
  require(z.testzip() is None,'PCB ZIP CRC failure')
  for p in fab_files:require(hashlib.sha256(z.read('manufacturing/'+p)).hexdigest()==sha(ROOT/pcb_dir/'package'/p),'Fabrication file mismatch '+p)
 drawing=read('product/matrix-assembly-diagrams/source-checks.json');require(drawing['pcb_release']==pcb_id,'Drawing release mismatch')
 for p,h in drawing['source_hashes'].items():verify_hash(p,h)
 require(len(rows('product/matrix-assembly-diagrams/soldering-map.csv'))==19,'Wire map count mismatch')
 electrical=rows('product/matrix-assembly-diagrams/unpowered-check-record.csv');require(len(electrical)==59 and all(not r['实测'] and r['结果']=='待测' for r in electrical),'Electrical observations overwritten')
 subprocess.run([sys.executable,str(ROOT/'product/final-assembly/generate.py'),'--check-only'],check=True)
 assembly=read('product/final-assembly/source-checks.json');require(assembly['cad_export_id']==receipt['exportId'] and assembly['row_count']==154 and assembly['firmware_version']=='0.3.0','Assembly record mismatch')
 shopping=read('product/purchasing/matrix/hand-assembly-shopping.json');require(shopping['source_bom_sha256']==sha(ROOT/'product/bom.json') and shopping['source_requirements_sha256']==sha(ROOT/'product/requirements.json'),'Purchasing input hash stale')
 require(len(shopping['items'])==30 and {i for row in shopping['items'] for i in row['bom_item_ids'].split(',')}==items.keys(),'Purchasing coverage mismatch')
 shopping_csv=rows('product/purchasing/matrix/hand-assembly-shopping.csv');require(len(shopping_csv)==30,'Shopping CSV count')
 for a,b in zip(shopping_csv,shopping['items']):require(all(str(b[k])==v for k,v in a.items()),'Shopping CSV differs')
 procurement=read('product/purchasing/matrix/procurement-record.json')
 for e in procurement['files']:verify_hash('product/purchasing/matrix/'+e['name'],e['sha256'])
 selected=set()
 def add(p):
  f=ROOT/p;require(f.is_file(),'Missing delivery input '+p);selected.add(f)
 def tree(p,filter_=None):
  for f in (ROOT/p).rglob('*'):
   if f.is_file() and '__pycache__' not in f.parts and f.suffix not in ['.pyc','.tmp-design'] and f.name!='.DS_Store' and (filter_ is None or filter_(f)):selected.add(f)
 for p in ['README.md','project.manifest.json','design/assembly.json','design/enclosure/README.md','product/README.md','product/requirements.json','product/constraints.json','product/contract.json','product/bom.json','product/bom.csv','product/component-selection.json','product/type-c-controller-assembly.md','product/type-c-controller-wiring.csv','product/type-c-controller-selection.json','product/type-c-integration-verification.json','product/type-c-port-refinement.json','product/type-c-reference-repair.json','product/type-c-reference-repair.md','product/repair_typec_reference.py','product/harness-routing.md','product/harness-routing-verification.json','product/keycap-usability-verification.json','product/matrix-pcb-verification.json',fwzip,'product/lcd-upgrade.md',binding['receipt'],step['path'],'manufacturing/matrix/release-index.json']:
  add(p)
 tree('design/enclosure/source',lambda p:p.parent.name!='assets' or p.stem in active_assets)
 for p in ['design/matrix','design/firmware/source','design/firmware/tests',fwdir,'product/final-assembly','product/print-preparation','product/purchasing/matrix'] :tree(p)
 for p in ['README.md','bootstrap.py','build.py','check_wiring.py','dependencies.lock.json']:add('design/firmware/'+p)
 tree(pcb_dir)
 for p in ['README.md','build_delivery.py','generate_models.py','sync_delivery_records.py','verify_mesh_features.py','verify_case_meshes.py','verify_print_preparation.py','export_compatibility.py','model-manifest.json','print-plan.csv','design-verification.json','mesh-feature-checks.json','case-mesh-checks.json','harness-delivery-addendum.json','matrix-fabrication.zip']:add('product/production/'+p)
 tree('product/production/models');tree('product/production/history',lambda p:p.suffix=='.json')
 diagram_names=['01-component-orientation','02-j1-j10-to-controller','03-lcd-orientation-and-wiring','04-details-and-unpowered-checks']
 for n in diagram_names:
  for ext in ['svg','png']:add('product/matrix-assembly-diagrams/'+n+'.'+ext)
 for p in ['generate.py','README.md','guided-soldering.md','soldering-map.csv','unpowered-check-record.csv','source-checks.json','calckey-matrix-pcb-assembly.pdf']:add('product/matrix-assembly-diagrams/'+p)
 for p in ['gdm0103-specification.pdf','ht1621-v340.pdf','vishay-1n4148.pdf','eda-keypad-reference.md','gateron-ks9/KS-9 Switch KS-9H10B045NN-X14-FB.stp','type-c-controllers/waveshare-rp2350-plus.step','type-c-controllers/waveshare-rp2350-plus-nurbs-repaired.step','type-c-controllers/waveshare-rp2350-plus-schematic.pdf','type-c-controllers/waveshare-plus-pinout.jpg','type-c-controllers/waveshare-plus-mechanical.jpg']:add('product/references/'+p)
 files=[{'file':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(selected)]
 inventory={'printed_parts':30,'regenerated_meshes':4,'reused_meshes':26,'PLA_parts':4,'PETG_parts':26,'bom_rows':31,'shopping_rows':30,'matrix_leads':10,'lcd_leads':5,'wire_installed_m':2.25,'wire_purchase_default_m':3,'firmware_version':'0.3.0','firmware_board':fw['board'],'firmware_test_counts':fw['host_test_counts'],'wiring_pdf_pages':4,'pcb_unpowered_record_rows':59,'whole_device_unpowered_rows':154,'fabrication_files':len(fab_files)}
 manifest={'generated_utc':datetime.now(timezone.utc).isoformat(),'revision':receipt['revision'],'export_id':receipt['exportId'],'source_receipt':binding['receipt'],'pcb_release_id':pcb_id,'pcb_build_id':pcb['buildId'],'inventory_checks':inventory,'files':files,'manifest_self_hash_excluded':True,'printer_started':False,'powered':False,'flashed':False,'hardware_tested':False}
 mp=OUT/'package-manifest.json';expected={x['file'] for x in files}|{str(mp.relative_to(ROOT))}
 if check_only:
  old=read('product/production/package-manifest.json');require(old['files']==files and old['inventory_checks']==inventory and old['export_id']==receipt['exportId'],'Complete package manifest stale')
 else:
  mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');temporary=TARGET.with_suffix('.tmp.zip')
  with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
   for p in sorted(selected|{mp}):z.write(p,str(p.relative_to(ROOT)))
  with zipfile.ZipFile(temporary) as z:require(z.testzip() is None,'Complete ZIP CRC failure')
  temporary.replace(TARGET);TARGET.with_suffix('.zip.sha256').write_text(sha(TARGET)+'  '+TARGET.name+'\n')
 with zipfile.ZipFile(TARGET) as z:
  require(z.testzip() is None and set(z.namelist())==expected,'Complete ZIP inventory/CRC mismatch')
  for n in expected:require(hashlib.sha256(z.read(n)).hexdigest()==sha(ROOT/n),'ZIP bytes differ from delivery '+n)
 require(TARGET.with_suffix('.zip.sha256').read_text().split()[0]==sha(TARGET),'ZIP sidecar hash mismatch')
 print('PASS Type-C complete package: 30 closed STL, current CAD/STEP and repaired reference, PCB release, 31 BOM / 30 purchasing rows, 154 pending checks, v0.3.0 firmware. All file SHA256 and ZIP CRC checks pass.')
 print('ZIP entries',len(expected),'bytes',TARGET.stat().st_size,'sha256',sha(TARGET))
 print('No printing, slicing, power, flashing, ordering or Git commit performed.')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--check-only',action='store_true');main(p.parse_args().check_only)
