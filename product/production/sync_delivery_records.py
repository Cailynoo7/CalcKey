"""Synchronize verified conversion, unchanged assembly, procurement and docs.

No CAD build, PCB generation, printing, electrical test or device contact.
"""
import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
def read(p):return json.loads((ROOT/p).read_text())
def sha(p):return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
def write(p,d):(ROOT/p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')

def main():
    models=read('product/production/model-manifest.json')
    bind=models['current_binding'];receipt=read(bind['receipt'])
    feature=read('product/production/mesh-feature-checks.json')
    assert feature['export_id']==receipt['exportId']==bind['export_id']
    prior_path='product/production/history/matrix-before-keycap-cad-receipt.json'
    prior=read(prior_path)
    unchanged=sorted(n for n in receipt['shapeHashes'] if not n.startswith('key_'))
    assert len(unchanged)==12
    for n in unchanged:assert receipt['shapeHashes'][n]==prior['shapeHashes'][n],n
    step=next(x for x in receipt['artifacts'] if x['role']=='model/step')
    assert sha(step['path'])==step['sha256']
    keycaps=read('product/keycap-usability-verification.json')
    assert keycaps['revision']==receipt['revision']
    keycaps.setdefault('measurement_original_export_id',keycaps['export_id'])
    keycaps.update(export_id=receipt['exportId'],export_receipt=bind['receipt'],
                   step_sha256=step['sha256'],exported_state_hash=receipt['stateHash'])
    keycaps['limitations']=[x for x in keycaps['limitations'] if not x.startswith('Previous STL')]
    keycaps['mesh_feature_record']='product/production/mesh-feature-checks.json'
    write('product/keycap-usability-verification.json',keycaps)
    pcb=read('product/matrix-pcb-verification.json')
    assert pcb['cad_revision']==prior['revision']
    pcb['current_assembly_binding']={'cad_revision':receipt['revision'],
        'cad_export_id':receipt['exportId'],'receipt':bind['receipt'],
        'baseline_receipt':prior_path,'retained_inspection_revision':pcb['cad_revision'],
        'unchanged_objects':unchanged,
        'scope':'PCB, case, Pico, lens, fasteners and folding feet exactly unchanged; 20 caps checked separately on current revision'}
    pcb['cad_export_binding_note']='Top-level cad_revision and cad_export_id identify retained historical inspections; current_assembly_binding identifies the present handoff and its exact unchanged-object comparison.'
    write('product/matrix-pcb-verification.json',pcb)
    limits=list(dict.fromkeys(keycaps['limitations']+pcb['limitations']))
    write('product/production/design-verification.json',{
        'date':'2026-11-06','design_id':'enclosure','revision':receipt['revision'],
        'export_id':receipt['exportId'],'source_receipt':bind['receipt'],
        'pcb_release_id':pcb['pcb_release_id'],'printed_parts':28,
        'mesh_binding':'product/production/model-manifest.json',
        'geometry_checks':{
            'current_keycaps':{'path':'product/keycap-usability-verification.json','revision':keycaps['revision']},
            'actual_stl_features':{'path':'product/production/mesh-feature-checks.json','checks':feature['checks']},
            'retained_pcb_assembly':{'path':'product/matrix-pcb-verification.json','binding':pcb['current_assembly_binding']},
            'unchanged_non_keycap_meshes':8},
        'limitations':limits,'physical_print_trial_skipped_by_user':True,
        'device_actions':{'printing_started':False,'flashed':False,'powered':False}})
    p='product/purchasing/matrix/hand-assembly-shopping.json';shopping=read(p)
    shopping['source_bom_sha256']=sha('product/bom.json')
    shopping['source_requirements_sha256']=sha('product/requirements.json')
    for row in shopping['items']:
        if row['bom_item_ids']=='keycaps':
            row['notes']='20只新版正式键帽，含5键浅圆定位凹点和Enter/=双行标识；使用同版STEP/STL，PETG、0.2mm喷嘴/0.1mm层高，不另做试片。'
    shopping['keycap_cad_revision']=receipt['revision']
    shopping['keycap_export_id']=receipt['exportId']
    write(p,shopping)
    path=ROOT/'product/purchasing/matrix/hand-assembly-shopping.csv'
    with path.open(encoding='utf-8-sig',newline='') as f:fields=csv.DictReader(f).fieldnames
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fields);w.writeheader();w.writerows(shopping['items'])
    p='product/purchasing/matrix/procurement-record.json';record=read(p)
    record['checks']['printed_parts_unchanged']=8
    record['checks']['updated_keycap_meshes']=20
    record['checks']['printed_parts_total']=28
    record['keycap_cad_revision']=receipt['revision']
    record['actions']['source_bom_modified']=False
    for row in record['files']:row['sha256']=sha('product/purchasing/matrix/'+row['name'])
    write(p,record)
    path=OUT/'README.md';s=path.read_text()
    if s.startswith('> '):s=s.split('\n\n',1)[1]
    s=s.replace('STL保留原始STEP转换来源，并通过旧/当前导出记录的28件形状哈希与放置一致性绑定当前装配，',
                '20个键帽STL由当前整机STEP重新转换；另外8件保留原始转换来源，经逐件形状、安装位置和网格字节一致性绑定当前装配，')
    s=s.replace('generate_models.py只读取指定交付记录及对应STEP转换网格；几何未变时rebind_meshes.py核对28件形状哈希、放置和旧网格哈希，以保留原始转换来源的方式绑定当前导出。',
                'generate_models.py只读取交付STEP，用--keycaps-only重新转换20帽并严格核对复用的8件；verify_mesh_features.py直接读取STL检查5键凹点深度与Enter/=两行槽底。sync_delivery_records.py保留旧装配检查revision并验证未变物体，不将旧检查改写成新实测。')
    start=s.find('本次网格绑定可用以下命令复核')
    if start!=-1:s=s[:start]
    s += ('\n## 键帽网格与复核\n\n20帽采用Arial Bold凹刻：数字/运算符4.8mm、文字3.3mm，深0.35mm；字号不是实际字形高度。5键直径2mm、深0.35mm球面凹点，Enter与=上下双行。全体维持18.2×18.2×7mm外廓及原十字插座。转换后对真实STL表面测得凹点深度并核对两行槽底；20帽均为闭合网格，单位mm、100%比例、顶面向下、Z=0。\n\n'
          '球面极点可能导出重复顶点的零面积三角片；转换器仅移除严格重复顶点的零面积片，再检查全部网格边均由两面共享，不移动顶点、不补洞、不改变有效表面。8个非键帽网格经导出形状与放置完全一致后复用。\n\n'
          '使用带build123d 0.10.0的CAD Python执行网格转换；其余核验、同步和打包脚本使用Python标准库。以下命令只生成/核对文件：\n\n```sh\n'
          f'python product/production/generate_models.py {bind["receipt"]} --keycaps-only\n'
          'python3 product/production/verify_mesh_features.py\npython3 product/production/sync_delivery_records.py\npython3 product/production/build_delivery.py\npython3 product/production/build_delivery.py --check-only\n```\n\n'
          '完整包使用独立制板ZIP与PCB不可变发布逐文件核对，不需要重新布线或创建订单。--check-only核对已交付ZIP的目录、逐文件字节、CRC及CAD/PCB/固件和采购绑定，不依赖缓存，不写设备。新版STL已包含定位凹点和双标识，不与旧字形网格混用。\n')
    path.write_text(s)
    path=ROOT/'README.md';s=path.read_text()
    old='键帽CAD已增加5键浅圆定位凹点、Enter/=双标识和统一加粗排版，以当前STEP为准。此前完整设计ZIP及其20键帽STL仍为上一版字形，等待重新转换和打包，不能作为本次新键帽制造文件；8个其他打印件和矩阵PCB未改动。'
    new='20个键帽STL已与当前STEP同步，包含5键浅圆定位凹点、Enter/=双标识和统一加粗排版；完整制作ZIP按同一版本绑定CAD、采购、PCB制造和LCD固件记录。8个其他打印件与矩阵PCB未改动，网格经一致性核对后复用。'
    assert old in s or new in s
    path.write_text(s.replace(old,new))
    print('Synchronized current keycap meshes, retained PCB evidence, purchasing and production instructions; no device actions.')

if __name__=='__main__':main()
