"""Bind Type-C production documents to a verified handoff; never run hardware."""
import argparse,csv,hashlib,json,subprocess,sys
from pathlib import Path
from verify_mesh_features import verify as verify_keycaps
from verify_case_meshes import verify as verify_cases
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent

def read(p):return json.loads((ROOT/p).read_text())
def write(p,d):(ROOT/p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
def csv_write(p,rows,fields):
 with (ROOT/p).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)

def main(receipt_path):
 r=read(receipt_path);m=read('product/production/model-manifest.json');step=next(a for a in r['artifacts'] if a['role']=='model/step')
 assert m['revision']==r['revision'] and m['export_id']==r['exportId'] and sha(step['path'])==step['sha256']
 assert len(m['meshes'])==30 and r['status']=='handoff'
 binding={'receipt':receipt_path,'revision':r['revision'],'export_id':r['exportId'],'step_sha256':step['sha256']}
 features,cases=verify_keycaps(),verify_cases()
 write('product/production/mesh-feature-checks.json',features);write('product/production/case-mesh-checks.json',cases)
 repair=read('product/type-c-reference-repair.json')
 assert r['assetHashes']['pico2']==repair['output_sha256']
 repair['current_package_handoff']=binding;write('product/type-c-reference-repair.json',repair)
 integration=read('product/type-c-integration-verification.json');integration['current_package_handoff']=binding
 integration['manufacturing_package']='Current Type-C complete package; authoritative inventory in production/package-manifest.json'
 write('product/type-c-integration-verification.json',integration)
 pcb=read('product/matrix-pcb-verification.json');pcb['current_assembly_binding']={**binding,'cad_revision':r['revision'],'cad_export_id':r['exportId'],'scope':'Released matrix asset and position unchanged; Type-C controller clearances in type-c-integration-verification.json','pcb_step_sha256':r['assetHashes']['matrix_pcb']}
 write('product/matrix-pcb-verification.json',pcb)
 caps=read('product/keycap-usability-verification.json');caps['current_assembly_binding']={**binding,'measurement_revision':caps['revision'],'baseline_receipt':'product/production/history/before-typec-cad-receipt.json','all_20_keycap_shapes_unchanged':True};write('product/keycap-usability-verification.json',caps)
 harness=read('product/harness-routing-verification.json');harness['current_handoff_binding']={**binding,'measurement_revision':harness['revision'],'scope':'Five retained tape bridges only; revised Type-C case/controller and wire budgets use current integration record','current_type_c_checks':'product/type-c-integration-verification.json'};write('product/harness-routing-verification.json',harness)
 pcb_id=pcb['pcb_release_id']
 write('product/production/harness-delivery-addendum.json',{'cad_export':binding,'pcb_release_id':pcb_id,'firmware_version':'0.3.0','mesh_delivery':{'manifest':'product/production/model-manifest.json','regenerated':['base','top','controller_clamp_a','controller_clamp_b'],'unchanged_meshes':26},'assembly_delivery':{'guide':'product/final-assembly/README.md','blank_record':'product/final-assembly/unpowered-checklist.csv'},'device_actions':{'printed':False,'powered':False,'flashed':False}})
 write('product/production/design-verification.json',{'design_id':'enclosure','revision':r['revision'],'export_id':r['exportId'],'source_receipt':receipt_path,'pcb_release_id':pcb_id,'printed_parts':30,'geometry_checks':{'retained_keycap_measurements':{'path':'product/keycap-usability-verification.json','measurement_revision':caps['revision']},'type_c_assembly':'product/type-c-integration-verification.json','reference_repair':'product/type-c-reference-repair.json','actual_stl_case_features':'product/production/case-mesh-checks.json','actual_stl_keycap_features':'product/production/mesh-feature-checks.json','regenerated_meshes':4,'unchanged_meshes':26},'limitations':['Physical fit, board thickness, clamp retention, print shrinkage and strength remain untested.','GDM0103 uses vendor drawing envelopes, not an exact board model.','Flexible wires and tape holding force are not physically verified.','No printed fit test, electrical power or flashing performed.'],'device_actions':{'printed':False,'powered':False,'flashed':False}})
 shopping=read('product/purchasing/matrix/hand-assembly-shopping.json');shopping.update(source_bom_sha256=sha('product/bom.json'),source_requirements_sha256=sha('product/requirements.json'),enclosure_cad_revision=r['revision'],enclosure_export_id=r['exportId'])
 for row in shopping['items']:
  if row['category']=='打印件' or any(k in row['bom_item_ids'] for k in ['enclosure_base','enclosure_top','controller_clamp']):
   row['notes']='采用Type-C版30件模型清单，mm/100%；主壳、底盖和两只压桥来自当前STEP，其余26件经形状、安装位置和字节核对复用。'
 write('product/purchasing/matrix/hand-assembly-shopping.json',shopping)
 path=ROOT/'product/purchasing/matrix/hand-assembly-shopping.csv'
 with path.open(encoding='utf-8-sig',newline='') as f:fields=csv.DictReader(f).fieldnames
 csv_write('product/purchasing/matrix/hand-assembly-shopping.csv',shopping['items'],fields)
 procurement=read('product/purchasing/matrix/procurement-record.json');procurement['checks'].update(current_type_c_stl_generated=True,regenerated_meshes=4,reused_meshes=26,printed_parts_total=30)
 procurement['harness_addendum'].update(enclosure_export_id=r['exportId'],source_bom_sha256=sha('product/bom.json'),regenerated_meshes=['base','top','controller_clamp_a','controller_clamp_b'])
 for item in procurement['files']:item['sha256']=sha('product/purchasing/matrix/'+item['name'])
 write('product/purchasing/matrix/procurement-record.json',procurement)
 # Existing printer defaults retained; no slicer or machine is contacted.
 settings='product/print-preparation/part-settings.csv'
 with (ROOT/settings).open(encoding='utf-8-sig',newline='') as f:reader=csv.DictReader(f);fields=reader.fieldnames;old={x['object_id']:x for x in reader}
 rows=[]
 for mesh in m['meshes']:
  n=mesh['object_id'];row=dict(old[n] if n in old else old['top'])
  row.update(object_id=n,stl=mesh['file'],stl_sha256=mesh['sha256'],material=mesh['material'],nozzle_mm=mesh['nozzle_mm'],layer_mm=mesh['layer_mm'],applied_rotation_deg_xyz=json.dumps(mesh['local_print_rotation_deg']),bbox_mm='×'.join(f'{v:.3f}' for v in mesh['bbox_mm']))
  row['support_exclusions']=row['support_exclusions'].replace('Pico','主控')
  if n.startswith('controller_clamp'):
   row.update(name='主控压桥'+n[-1].upper(),infill_percent=100,orientation_already_in_stl='压脚向下、沉孔向上；已落Z=0',support_recommendation='仅非接触桥底酌情局部支撑；保留清理路径，不支撑压脚贴胶面',support_exclusions='螺钉沉孔、板边接触面和绝缘胶片面',cleanup_focus='去毛刺后贴0.15mm绝缘胶片，禁止拧紧压弯主控')
  if n=='base':row['support_exclusions']+='；Type-C孔与接口立台、八处主控绝缘贴面'
  rows.append(row)
 csv_write(settings,rows,fields)
 subprocess.run([sys.executable,str(ROOT/'product/final-assembly/generate.py')],check=True)
 guide=ROOT/'product/print-preparation'
 inputs=['product/production/model-manifest.json','product/production/print-plan.csv','product/production/case-mesh-checks.json','product/production/mesh-feature-checks.json','product/production/design-verification.json','design/enclosure/source/design.json','design/enclosure/source/parts/base/000-base.py','design/enclosure/source/parts/top/000-top.py',receipt_path]
 checks={'kind':'printing_advice_document_consistency','current_cad_binding':binding,'counts':{'total_parts':30,'PLA_parts':4,'PETG_parts':26},'input_sha256':{p:sha(p) for p in inputs},'mesh_sha256':{x['file']:x['sha256'] for x in m['meshes']},'document_sha256':{p:sha(p) for p in [settings,'product/print-preparation/README.md']},'physical_printing':False}
 write('product/print-preparation/source-checks.json',checks)
 print('PASS Type-C production binding: 30 meshes, preserved historical measurements, updated blank records and purchase/print document hashes.')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('receipt');main(p.parse_args().receipt)
