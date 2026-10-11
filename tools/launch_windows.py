#!/usr/bin/env python3
"""Prepare and launch the existing combined Forge host on Windows x64."""
import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

JAVA_URL = ('https://github.com/adoptium/temurin8-binaries/releases/download/jdk8u504-b01/'
            'OpenJDK8U-jre_x64_windows_hotspot_8u504b01.zip')
JAVA_SHA256 = '82e2cdc6693737c5998445b31f69668fa0da77c7705121053f6508ac84961123'
JAVA_EXE_SHA256 = '46df95bb47e2ba2b10736cee2ab543289c66021611f1ec67d0d55d5128228c20'
HOST_NAME = 'Decraft-combined-linux-host-and-sources.zip'
HOST_SHA256 = '72d802e117fd6c69d1e20d6f5f26a5a5906f5852158545cd826775503cd6d8d2'
ORIGINAL_LAUNCHER_SHA256 = 'ee2ed7492be9da20165603d7d85a93bd68dc170357b248e9fced9bbb9fff5758'
ROOT = Path(__file__).resolve().parent.parent


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def game_member(name):
    """Extract launch dependencies, avoiding unrelated recovered source trees."""
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
        raise ValueError('Unsafe archive path: ' + name)
    return (name.startswith('runtime/') or
            name.startswith('tools/') and name.endswith('.py') or
            name.startswith(('assets/original-data/bt3/', 'assets/original-data/halo2/',
                             'assets/original-data/digimon/')) or
            name in {'fusion/forge-bridge-build.json',
                     'build/fusion/forge/decraft-bridge-0.1.0.jar',
                     'build/fusion/windows/decraft_fusion.dll'})


def extract_host(archive, destination):
    if destination.exists():
        raise RuntimeError('Existing game directory preserved: ' + str(destination))
    print('Verifying the downloaded host archive...', flush=True)
    if digest(archive) != HOST_SHA256:
        raise ValueError('The host archive is incomplete or differs from the verified release')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.decraft-extract-', dir=destination.parent))
    try:
        with zipfile.ZipFile(archive) as package:
            members = [entry for entry in package.infolist() if game_member(entry.filename)]
            needed = sum(entry.file_size for entry in members)
            if shutil.disk_usage(destination.parent).free < needed + 128 * 1024 * 1024:
                raise RuntimeError('Not enough free disk space to extract the game; need about ' +
                                   str((needed // (1024 * 1024)) + 128) + ' MiB')
            print('Extracting the playable host and saved worlds...', flush=True)
            for entry in members:
                package.extract(entry, temporary)
        if destination.exists():
            raise RuntimeError('Existing game directory preserved: ' + str(destination))
        temporary.rename(destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def find_game(root):
    candidates = [root, root / 'Decraft-game']
    candidates.extend(sorted(p for p in root.iterdir() if p.is_dir() and
                             not p.name.startswith('.')))
    for candidate in candidates:
        if ((candidate / 'runtime/forge-launch.json').is_file() and
                (candidate / 'tools/fusion.py').is_file()):
            return candidate
    archive = root / HOST_NAME
    if not archive.exists() and (root / 'assemble.py').is_file():
        print('Reassembling the verified game archive...', flush=True)
        subprocess.run([sys.executable, str(root / 'assemble.py'), '--archive', HOST_NAME], check=True)
    if archive.is_file():
        destination = root / 'Decraft-game'
        extract_host(archive, destination)
        return destination
    raise RuntimeError('Extract this launch fix into the game folder (the one containing runtime and tools), '
                       'or into the downloaded branch folder containing assemble.py and chunks.')


def prepare_java(game, supplied=None):
    if supplied is not None:
        java = Path(supplied).resolve()
    else:
        directory = game / 'runtime/java/windows'
        java = directory / 'jdk8u504-b01-jre/bin/java.exe'
        if not java.is_file():
            if directory.exists():
                raise RuntimeError('Existing incomplete Windows Java directory preserved: ' + str(directory))
            directory.parent.mkdir(parents=True, exist_ok=True)
            temporary = Path(tempfile.mkdtemp(prefix='.windows-java-', dir=directory.parent))
            try:
                archive = temporary / 'java.zip'
                print('Downloading verified Windows Java 8 (40 MB)...', flush=True)
                with urllib.request.urlopen(JAVA_URL, timeout=60) as response, archive.open('xb') as out:
                    shutil.copyfileobj(response, out)
                if digest(archive) != JAVA_SHA256:
                    raise RuntimeError('Windows Java archive failed SHA-256 verification')
                with zipfile.ZipFile(archive) as package:
                    for entry in package.infolist():
                        name = PurePosixPath(entry.filename)
                        if name.is_absolute() or '..' in name.parts or '\\' in entry.filename or ':' in entry.filename:
                            raise ValueError('Unsafe Java archive path')
                    package.extractall(temporary / 'extracted')
                if directory.exists():
                    raise RuntimeError('Existing Windows Java directory preserved')
                (temporary / 'extracted').rename(directory)
            finally:
                shutil.rmtree(temporary)
        if digest(java) != JAVA_EXE_SHA256:
            raise RuntimeError('Windows Java executable differs from the verified runtime; existing file preserved')
    probe = subprocess.run([str(java), '-XshowSettings:properties', '-version'],
                           capture_output=True, text=True, timeout=30)
    text = probe.stdout + probe.stderr
    if probe.returncode or 'java.version = 1.8.' not in text or 'sun.arch.data.model = 64' not in text:
        raise RuntimeError('The game needs 64-bit Java 8. Java check failed:\n' + text[-4000:])
    return java


def install_launcher_update(game, root=ROOT):
    """Apply this repair when the host was extracted from the older archive."""
    source = root / 'tools/launch_combined.py'
    destination = game / 'tools/launch_combined.py'
    if source.resolve() == destination.resolve():
        return
    current = digest(source)
    existing = digest(destination)
    if current == existing:
        return
    if existing != ORIGINAL_LAUNCHER_SHA256:
        raise RuntimeError('A different existing launcher is preserved: ' + str(destination) +
                           '. Extract the repair into a separate copy or inspect your custom changes first.')
    backups = game / 'tools/.decraft-launcher-backups'
    backups.mkdir(exist_ok=True)
    backup = backups / (existing + '.py')
    if backup.exists():
        if digest(backup) != existing:
            raise RuntimeError('Existing launcher backup differs; game launcher preserved')
    else:
        with backup.open('xb') as out, destination.open('rb') as old:
            shutil.copyfileobj(old, out)
    temporary = destination.with_suffix('.py.windows-update')
    with temporary.open('xb') as out, source.open('rb') as repaired:
        shutil.copyfileobj(repaired, out)
    if digest(destination) != existing:
        temporary.unlink()
        raise RuntimeError('Game launcher changed during update; existing file preserved')
    temporary.replace(destination)


def prepare_config(game, java):
    sys.path.insert(0, str(game / 'tools'))
    from launch_combined import load_config, validate_config
    config = load_config(game / 'runtime/forge-launch.json')
    config['java'] = str(java)
    # The companion service binds IPv4 loopback. This also avoids legacy
    # Java 8 adapter-prefix enumeration failures with Wine/IPv6 interfaces.
    config['prefer_ipv4_stack'] = True
    config['natives'] = str(game / 'runtime/host/bin/natives')
    for name in ('lwjgl64.dll', 'OpenAL64.dll', 'jinput-dx8_64.dll', 'jinput-raw_64.dll'):
        if not (Path(config['natives']) / name).is_file():
            raise RuntimeError('Missing Windows graphics/audio/input library: ' + name)
    if not (game / 'build/fusion/windows/decraft_fusion.dll').is_file():
        raise RuntimeError('Missing Windows shared runtime DLL; use the host package rather than the source SDK')
    validate_config(config)
    destination = game / 'runtime/forge-launch-windows.json'
    # This separate generated file leaves the original Linux config untouched.
    destination.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-root', type=Path, default=ROOT)
    parser.add_argument('--java', type=Path, help='Optional existing 64-bit Java 8 executable')
    parser.add_argument('--check', action='store_true', help='Prepare and check dependencies without opening the game')
    parser.add_argument('--seconds', type=int, help='Bounded test; omit for normal play')
    args = parser.parse_args()
    if args.seconds is not None and not 1 <= args.seconds <= 1800:
        parser.error('Diagnostic duration must be 1..1800 seconds')
    if os.name != 'nt' or struct.calcsize('P') != 8:
        raise RuntimeError('Launch-Game.cmd requires 64-bit Windows and 64-bit Python')
    game = find_game(args.game_root.resolve())
    print('Game folder: ' + str(game), flush=True)
    install_launcher_update(game)
    java = prepare_java(game, args.java)
    config = prepare_config(game, java)
    from fusion_runtime import Kernel
    kernel = Kernel()
    if kernel.lib.fx_abi_version() != 1:
        raise RuntimeError('Incompatible Windows shared runtime')
    print('Windows Java, graphics libraries and shared runtime passed startup checks.', flush=True)
    if args.check:
        return 0
    from launch_combined import CombinedLaunch
    print('Starting the modpack. First startup can take 10 minutes. Keep this window open.', flush=True)
    launch = CombinedLaunch(config, game / 'runtime/fusion.sqlite3', game / 'runtime/logs')
    code = launch.run(seconds=args.seconds)
    print('Launch logs: ' + str(launch.run_directory), flush=True)
    if code:
        print('Startup failed: ' + str(launch.result.get('error', launch.result['status'])), flush=True)
        minecraft = launch.run_directory / 'minecraft.log'
        if minecraft.is_file():
            with minecraft.open(encoding='utf-8', errors='replace') as stream:
                from collections import deque
                print(''.join(deque(stream, maxlen=35)), flush=True)
    return code


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print('WINDOWS LAUNCH ERROR: ' + str(error), file=sys.stderr, flush=True)
        sys.exit(1)
