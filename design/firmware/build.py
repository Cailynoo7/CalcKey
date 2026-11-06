#!/usr/bin/env python3
"""Run host tests, build Pico 2 firmware, validate UF2, and stage the release."""
import datetime
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SOURCE=HERE/'source'
VERSION=re.search(r'project\(calckey VERSION ([0-9.]+)',(SOURCE/'CMakeLists.txt').read_text()).group(1)
CACHE=ROOT/'.work/firmware-tools'
BUILD=ROOT/'.work/firmware-build'
TESTS=ROOT/'.work/firmware-tests'
RELEASE=HERE/'release'/('v'+VERSION)
TESTS.mkdir(parents=True,exist_ok=True)
def tool(env,relative,fallback):
    value=os.environ.get(env)
    if value: return Path(value).resolve()
    cached=CACHE/relative
    if cached.exists(): return cached
    found=shutil.which(fallback)
    if found: return Path(found)
    sys.exit('Missing '+fallback+'; run bootstrap.py first or set '+env)
cmake=tool('CALCKEY_CMAKE','python/cmake/data/bin/cmake','cmake')
ninja=tool('CALCKEY_NINJA','python/bin/ninja','ninja')
sdk=Path(os.environ.get('PICO_SDK_PATH',str(CACHE/'pico-sdk-2.2.0'))).resolve()
tinyusb=Path(os.environ.get('PICO_TINYUSB_PATH',str(CACHE/'tinyusb-0.18.0'))).resolve()
compiler=Path(os.environ.get('PICO_TOOLCHAIN_PATH',str(CACHE/'arm-gnu-toolchain-14.2.rel1-darwin-arm64-arm-none-eabi'))).resolve()
picotool_dir=Path(os.environ.get('CALCKEY_PICOTOOL_DIR',str(CACHE/'picotool-install/picotool'))).resolve()
host_cxx=os.environ.get('CXX_HOST','clang++')
commands=[]
def run(args):
    args=[str(x) for x in args]
    print('+',' '.join(args),flush=True)
    result=subprocess.run(args,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    print(result.stdout,end='',flush=True)
    commands.append({'command':args,'exit_code':result.returncode,'output':result.stdout})
    if result.returncode: sys.exit(result.returncode)
    return result.stdout
run([sys.executable,HERE/'check_wiring.py'])
host_flags=['-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g','-I',SOURCE]
for test,extra in [('core_tests',[]),('lcd_tests',['-I',HERE/'tests/fakes',SOURCE/'lcd.cpp'])]:
    run([host_cxx,*host_flags,SOURCE/'decimal.cpp',SOURCE/'application.cpp',*extra,HERE/'tests'/f'{test}.cpp','-o',TESTS/test])
    run([TESTS/test])
run([sys.executable,HERE/'tests/decimal_oracle.py'])
run([sys.executable,HERE/'tests/lcd_decimal_oracle.py'])
run([cmake,'-S',SOURCE,'-B',BUILD,'-G','Ninja','-DCMAKE_MAKE_PROGRAM='+str(ninja),
     '-DPICO_BOARD=pico2','-DPICO_SDK_PATH='+str(sdk),'-DPICO_TOOLCHAIN_PATH='+str(compiler),
     '-DPICO_TINYUSB_PATH='+str(tinyusb),'-Dpicotool_DIR='+str(picotool_dir),'-DCMAKE_BUILD_TYPE=Release'])
run([cmake,'--build',BUILD,'--parallel','6'])
info=run([picotool_dir/'picotool','info','-a',BUILD/'calckey.uf2'])
assert "'rp2350-arm-s'" in info and 'pico2' in info and 'CalcKey' in info and VERSION in info
size=run([compiler/'bin/arm-none-eabi-size',BUILD/'calckey.elf'])
uf2=(BUILD/'calckey.uf2').read_bytes()
assert len(uf2)%512==0
total=len(uf2)//512
addresses=[]
families=set()
payload_blocks=[]
ignored_blocks=0
for i in range(total):
    magic0,magic1,flags,address,length,block,blocks,family=struct.unpack_from('<8I',uf2,i*512)
    assert magic0==0x0a324655 and magic1==0x9e5d5157
    assert struct.unpack_from('<I',uf2,i*512+508)[0]==0x0ab16f30
    assert flags&0x2000 and length==256
    families.add(family)
    if family==0xe48bff57:
        # Official picotool prepends the RP2350-E10 absolute-family workaround.
        # It is an ignored block, not an additional application image page.
        assert i==0 and flags==0xa000 and block==0 and blocks==2
        assert uf2[i*512+32:i*512+288]==bytes([0xef])*256
        assert struct.unpack_from('<I',uf2,i*512+288)[0]==0x9957e304
        ignored_blocks+=1
    else:
        assert family==0xe48bff59 and flags==0x2000
        assert 0x10000000<=address<0x10400000 and address%256==0
        addresses.append(address);payload_blocks.append((block,blocks))
assert ignored_blocks<=1 and len(set(addresses))==len(addresses)
assert payload_blocks==[(i,len(addresses)) for i in range(len(addresses))]
RELEASE.mkdir(parents=True,exist_ok=True)
artifacts={}
for suffix in ('uf2','elf','bin'):
    source=BUILD/f'calckey.{suffix}'
    target=RELEASE/f'calckey-pico2-v{VERSION}.{suffix}'
    shutil.copy2(source,target)
    artifacts[target.name]={'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
inputs={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(HERE.rglob('*')) if p.is_file() and 'release' not in p.relative_to(HERE).parts and '__pycache__' not in p.parts}
for p in [ROOT/'design/enclosure/source/wiring.json',ROOT/'product/requirements.json',
          ROOT/'product/references/gdm0103-specification.pdf',ROOT/'product/references/ht1621-v340.pdf']:
    inputs[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
counts=[int(n) for c in commands for n in re.findall(r'PASS (\d+)',c['output'])]
report={'version':VERSION,'board':'pico2','platform':'rp2350-arm-s',
        'display':'GDM0103 / HT1621B, 3.3V','lcd_gpio':{'data':0,'wr':1,'cs':11},
        'display_cells':8,'flashed':False,'display_ack_available':False,
        'built_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'compiler':run([compiler/'bin/arm-none-eabi-gcc','--version']).splitlines()[0],
        'host_test_counts':counts,'uf2_blocks':total,'uf2_application_blocks':len(addresses),
        'uf2_rp2350_e10_ignored_blocks':ignored_blocks,'uf2_families':[hex(f) for f in sorted(families)],
        'picotool_info':info,'size_output':size,'hardware_tested':False,
        'artifacts':artifacts,'source_hashes':inputs,'commands':commands}
(RELEASE/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
shutil.copy2(HERE/'README.md',RELEASE/'README.md')
for name,license_file in [('pico-sdk-LICENSE.TXT',sdk/'LICENSE.TXT'),('tinyusb-LICENSE',tinyusb/'LICENSE')]:
    shutil.copy2(license_file,RELEASE/name)
package=ROOT/f'product/calckey-firmware-v{VERSION}.zip'
with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
    for item in sorted(RELEASE.iterdir()):
        if item.is_file(): z.write(item,f'CalcKey-v{VERSION}/'+item.name)
    for item in sorted(HERE.rglob('*')):
        if item.is_file() and 'release' not in item.relative_to(HERE).parts and '__pycache__' not in item.parts:
            z.write(item,f'CalcKey-v{VERSION}/project/'+str(item.relative_to(ROOT)))
    for item in [ROOT/'product/requirements.json',ROOT/'design/enclosure/source/wiring.json',
                 ROOT/'product/lcd-upgrade.md']:
        z.write(item,f'CalcKey-v{VERSION}/project/'+str(item.relative_to(ROOT)))
print('Verified Pico 2 UF2 and staged release artifacts.')
