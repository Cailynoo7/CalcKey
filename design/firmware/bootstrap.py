#!/usr/bin/env python3
"""Fetch hash-pinned firmware tools into project cache; no global installation."""
import hashlib
import json
import platform
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CACHE = ROOT / '.work/firmware-tools'
lock = json.loads((HERE/'dependencies.lock.json').read_text())
if platform.system() != 'Darwin' or platform.machine() != 'arm64':
    sys.exit('This bootstrap pins macOS arm64 tools. On another host supply SDK/toolchain/CMake via build.py environment variables; see README.')
CACHE.mkdir(parents=True, exist_ok=True)
downloads = CACHE/'downloads'
downloads.mkdir(exist_ok=True)
def digest(path):
    with path.open('rb') as f:
        h=hashlib.sha256()
        for block in iter(lambda: f.read(1024*1024), b''): h.update(block)
        return h.hexdigest()
for item in lock['archives']:
    archive = downloads/item['file']
    if not archive.exists():
        temporary = archive.with_suffix(archive.suffix+'.partial')
        print('Downloading',item['directory'],flush=True)
        with urllib.request.urlopen(item['url'], timeout=60) as response, temporary.open('wb') as output:
            while True:
                chunk=response.read(1024*1024)
                if not chunk: break
                output.write(chunk)
        temporary.replace(archive)
    if digest(archive) != item['sha256']:
        sys.exit('Archive hash mismatch: '+item['file'])
    destination=CACHE/item['directory']
    if not destination.exists():
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                path=Path(member.name)
                if path.is_absolute() or '..' in path.parts:
                    sys.exit('Unsafe archive path')
            tar.extractall(CACHE)
python_tools=CACHE/'python'
cmake=python_tools/'cmake/data/bin/cmake'
ninja=python_tools/'bin/ninja'
if not cmake.exists() or not ninja.exists():
    subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check',
                    '--no-cache-dir','--target',str(python_tools),
                    'cmake==3.31.6','ninja==1.11.1.4'],check=True)
picotool=CACHE/'picotool-install/picotool/picotool'
if not picotool.exists():
    build=ROOT/'.work/firmware-picotool'
    subprocess.run([str(cmake),'-S',str(CACHE/'picotool-2.2.0'),'-B',str(build),'-G','Ninja',
                    '-DCMAKE_MAKE_PROGRAM='+str(ninja),'-DPICO_SDK_PATH='+str(CACHE/'pico-sdk-2.2.0'),
                    '-DPICOTOOL_NO_LIBUSB=1','-DPICOTOOL_FLAT_INSTALL=1',
                    '-DCMAKE_INSTALL_PREFIX='+str(CACHE/'picotool-install')],check=True)
    subprocess.run([str(cmake),'--build',str(build),'--parallel','6','--target','install'],check=True)
print('Firmware build tools ready in project cache.')
