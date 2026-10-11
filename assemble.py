#!/usr/bin/env python3
"""Reassemble the verified Decraft release archives from downloaded chunks."""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def run(name=None):
    manifest=json.loads((ROOT/'transfer-manifest.json').read_text())
    if manifest['format']!=1:raise ValueError('Unsupported download manifest')
    archives=manifest['archives']
    if name:
        archives=[a for a in archives if a['archive']==name]
        if not archives:raise ValueError('Unknown archive name')
    for archive in archives:
        filename=archive['archive']
        if Path(filename).name!=filename or not filename.endswith('.zip'):raise ValueError('Invalid archive filename')
        target=ROOT/filename
        if target.exists():
            if digest(target)==archive['sha256']:print(filename+': already verified');continue
            raise ValueError('A different existing archive is preserved: '+filename)
        for part in archive['parts']:
            if not re.fullmatch(r'[0-9a-f]{64}',part['sha256']):raise ValueError('Invalid chunk hash')
            path=ROOT/'chunks'/(part['sha256']+'.bin')
            if not path.is_file() or path.stat().st_size!=part['bytes']:
                raise ValueError('Missing or incomplete download chunk: '+path.name)
        pending=target.with_suffix('.zip.joining');whole=hashlib.sha256();count=0
        try:
            with pending.open('xb') as out:
                for part in archive['parts']:
                    h=hashlib.sha256()
                    with (ROOT/'chunks'/(part['sha256']+'.bin')).open('rb') as source:
                        for block in iter(lambda:source.read(1024*1024),b''):
                            out.write(block);whole.update(block);h.update(block);count+=len(block)
                    if h.hexdigest()!=part['sha256']:raise ValueError('Chunk hash mismatch: '+part['name'])
            if count!=archive['bytes'] or whole.hexdigest()!=archive['sha256']:
                raise ValueError('Reassembled archive hash mismatch')
            if target.exists():raise ValueError('Existing destination preserved: '+filename)
            pending.rename(target)
        except Exception:
            # Remove only the temporary output created by this invocation.
            if pending.exists() and count:pending.unlink()
            raise
        print(filename+': verified '+str(count)+' bytes')
    print('Windows: double-click Launch-Game.cmd. Linux x64: extract the host ZIP and run ./launch-game.sh. Original campaigns/combat remain incomplete.')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',help='Optionally assemble only this archive filename')
    args=parser.parse_args();run(args.archive)
