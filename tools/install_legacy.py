#!/usr/bin/env python3
"""Assemble the hashed Legacy runtime, extract into a new folder and launch it."""
import hashlib
import json
from pathlib import Path,PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

def fetch_native_chunks(root,archive,base):
    chunks=root/'chunks';chunks.mkdir(exist_ok=True)
    for index,part in enumerate(archive['parts'],1):
        filename=part['sha256']+'.bin';destination=chunks/filename
        if len(part['sha256'])!=64 or any(c not in '0123456789abcdef' for c in part['sha256']):
            raise ValueError('Invalid native download hash')
        if destination.exists():
            if destination.stat().st_size!=part['bytes']:
                raise ValueError('Existing different download chunk preserved: '+filename)
            continue  # Reassembly checks existing bytes before accepting them.
        print('Downloading Legacy chunk '+str(index)+'/'+str(len(archive['parts']))+'...',flush=True)
        sha=hashlib.sha256();count=0
        with tempfile.NamedTemporaryFile(prefix='.native-chunk-',dir=chunks,delete=False) as out:
            pending=Path(out.name)
            try:
                with urllib.request.urlopen(base+filename,timeout=60) as response:
                    for block in iter(lambda:response.read(1024*1024),b''):
                        count+=len(block)
                        if count>part['bytes']:raise ValueError('Native download exceeds expected length')
                        sha.update(block);out.write(block)
                out.flush()
                if count!=part['bytes'] or sha.hexdigest()!=part['sha256']:
                    raise ValueError('Native download failed SHA-256 verification')
            except Exception:
                out.close();pending.unlink();raise
        if destination.exists():pending.unlink();raise RuntimeError('Existing chunk preserved')
        pending.rename(destination)

def install(root):
    sys.path.insert(0,str(root))
    import assemble
    name='Decraft-Legacy-Windows.zip'
    manifest=json.loads((root/'transfer-manifest.json').read_text())
    record=next(a for a in manifest['archives'] if a['archive']==name)
    if not (root/name).is_file() and manifest.get('legacy_download_base_url'):
        fetch_native_chunks(root,record,manifest['legacy_download_base_url'])
    assemble.run(name)
    archive=root/name;destination=root/'Decraft-Legacy'
    expected=next(a for a in manifest['archives'] if a['archive']==name)['sha256']
    if assemble.digest(archive)!=expected:raise ValueError('Legacy archive hash mismatch')
    # Existing installations and their save files are always retained.
    if not destination.exists():
        pending=Path(tempfile.mkdtemp(prefix='.legacy-extract-',dir=root))
        try:
            with zipfile.ZipFile(archive) as z:
                if shutil.disk_usage(root).free<sum(i.file_size for i in z.infolist())+128*1024*1024:
                    raise RuntimeError('Not enough free disk space to extract the native client')
                for entry in z.infolist():
                    p=PurePosixPath(entry.filename)
                    if p.is_absolute() or '..' in p.parts or '\\' in entry.filename or ':' in entry.filename:
                        raise ValueError('Unsafe Legacy archive path')
                z.extractall(pending)
            if destination.exists():raise RuntimeError('Existing Legacy installation preserved')
            pending.rename(destination)
        finally:
            if pending.exists():shutil.rmtree(pending)
    launcher=destination/'Launch-Legacy.exe'
    if not launcher.is_file():raise RuntimeError('Existing incomplete Legacy folder preserved. Rename it before installing again')
    print('Starting the native Legacy client...',flush=True)
    return subprocess.run([str(launcher)],cwd=destination).returncode

if __name__=='__main__':
    try:raise SystemExit(install(Path(__file__).resolve().parent.parent))
    except Exception as e:print('LEGACY INSTALL ERROR: '+str(e),file=sys.stderr);raise SystemExit(1)
