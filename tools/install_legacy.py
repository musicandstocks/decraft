#!/usr/bin/env python3
"""Assemble the hashed Legacy runtime, extract into a new folder and launch it."""
import hashlib
import json
from pathlib import Path,PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import zipfile

def install(root):
    sys.path.insert(0,str(root))
    import assemble
    name='Decraft-Legacy-Windows.zip';assemble.run(name)
    archive=root/name;destination=root/'Decraft-Legacy'
    manifest=json.loads((root/'transfer-manifest.json').read_text())
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
