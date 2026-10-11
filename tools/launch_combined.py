#!/usr/bin/env python3
"""Launch the original Forge host and the compiled shared runtime together."""
import argparse
import hashlib
import json
import os
import queue
import select
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from urllib.parse import quote

PROJECT = Path(__file__).resolve().parent.parent
BRIDGE = PROJECT / 'build/fusion/forge/decraft-bridge-0.1.0.jar'


class HostLock:
    """Prevent two launchers from opening the same host's saved worlds."""
    def __init__(self, directory):
        self.stream = (directory / '.decraft-launch.lock').open('a+b')
        self.stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                if not self.stream.read(1):
                    self.stream.write(b'0'); self.stream.flush()
                self.stream.seek(0)
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.stream.close()
            raise RuntimeError('Another combined launcher owns this game directory') from None

    def close(self):
        self.stream.close()


def validate_config(config):
    if 'prefer_ipv4_stack' in config and type(config['prefer_ipv4_stack']) is not bool:
        raise ValueError('prefer_ipv4_stack must be a boolean')
    for name in ('java', 'game_directory', 'classpath', 'natives', 'main_class', 'arguments'):
        if name not in config:
            raise ValueError('Launch configuration is missing ' + name)
    for name in ('classpath', 'arguments'):
        if not isinstance(config[name], list) or not all(isinstance(v, str) for v in config[name]):
            raise ValueError(name + ' must be an array of strings')
    if not isinstance(config['main_class'], str) or not config['main_class']:
        raise ValueError('Expected a Java main class')
    for name in ('java', 'game_directory', 'natives'):
        if not isinstance(config[name], str) or not Path(config[name]).exists():
            raise ValueError('Unavailable launch path: ' + name)
    if not Path(config['game_directory']).is_dir() or not Path(config['natives']).is_dir():
        raise ValueError('Game and native paths must be directories')
    for entry in config['classpath']:
        if not Path(entry).is_file():
            raise ValueError('Unavailable classpath file: ' + entry)


def load_config(path):
    """Portable packages resolve paths relative to the configuration file."""
    config = json.loads(path.read_text())
    base = path.resolve().parent
    for name in ('java', 'game_directory', 'natives'):
        if name in config: config[name] = str((base / config[name]).resolve())
    if 'classpath' in config:
        config['classpath'] = [str((base / entry).resolve()) for entry in config['classpath']]
    arguments = config.get('arguments', [])
    for index, flag in enumerate(arguments[:-1]):
        if flag in ('--gameDir', '--assetsDir'):
            arguments[index + 1] = str((base / arguments[index + 1]).resolve())
    return config


def install_bridge(directory):
    receipt = json.loads((PROJECT / 'fusion/forge-bridge-build.json').read_text())
    raw = BRIDGE.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != receipt['sha256']:
        raise RuntimeError('Bridge differs from its compiled build receipt; rebuild first')
    mods = directory / 'mods'; mods.mkdir(exist_ok=True)
    destination = mods / BRIDGE.name
    others = [p for p in mods.glob('decraft-bridge-*.jar') if p != destination]
    if others:
        raise RuntimeError('Other Decraft bridge versions preserved; use a separate runtime copy')
    if destination.exists():
        if destination.read_bytes() != raw:
            existing=hashlib.sha256(destination.read_bytes()).hexdigest()
            if existing not in receipt.get('prior_owned_bridge_sha256',[]):
                raise RuntimeError('Existing different bridge preserved; use a separate runtime copy')
            retained=directory/'.decraft-bridges';retained.mkdir(exist_ok=True)
            backup=retained/(existing+'.jar')
            if not backup.exists():shutil.copy2(destination,backup)
            elif hashlib.sha256(backup.read_bytes()).hexdigest()!=existing:
                raise RuntimeError('Existing bridge backup differs; installed bridge preserved')
            pending=destination.with_suffix('.jar.pending')
            with pending.open('xb') as stream:stream.write(raw)
            pending.replace(destination)
    else:
        with destination.open('xb') as stream:
            stream.write(raw)
    return {'path': str(destination), 'sha256': digest, 'original_mods_modified': False}


def event_summary(database, after=0):
    address = 'file:' + quote(str(database.resolve()), safe='/') + '?mode=ro'
    with sqlite3.connect(address, uri=True, timeout=5) as connection:
        count, maximum = connection.execute(
            'SELECT count(*), coalesce(max(id),0) FROM events WHERE id>?', (after,)).fetchone()
        rows = connection.execute('SELECT payload FROM events WHERE id>? ORDER BY id DESC LIMIT 8',
                                  (after,)).fetchall()
    events = [json.loads(row[0]) for row in reversed(rows)]
    return {'count': count, 'last_id': maximum,
            'recent_modpack_ticks': [e['ticks'] for e in events if e.get('module') == 'modpack'
                                    and e.get('event') == 'server_tick']}


class CombinedLaunch:
    def __init__(self, config, database, logs, port=0, virtual_display=False):
        self.config = config; self.database = Path(database).resolve()
        self.logs = Path(logs); self.logs.mkdir(parents=True, exist_ok=True)
        self.run_directory = Path(tempfile.mkdtemp(prefix='combined-', dir=self.logs))
        self.port = port; self.virtual_display = virtual_display
        self.env = os.environ.copy(); self.processes = []; self.streams = []
        self.client = None; self.server = None; self.reader = None; self.lock = None
        self.result = {'status': 'setup_failed', 'logs': str(self.run_directory),
                       'database': str(self.database), 'full_fusion_ready': False}

    def start(self, command, log, **kwargs):
        stream = (self.run_directory / log).open('w')
        self.streams.append(stream)
        process = subprocess.Popen(command, env=self.env, stdout=stream, stderr=stream, **kwargs)
        self.processes.append(process)
        return process

    def display(self):
        if not self.virtual_display:
            return
        if os.name != 'posix':
            raise ValueError('Virtual display is available only in the prepared Linux cloud')
        root = Path('/workspace/runtime-tools/root')
        modules = next((root / 'usr/lib').glob('pulse-*/modules'))
        self.env['LD_LIBRARY_PATH'] = ':'.join(str(p) for p in (
            root / 'usr/lib/x86_64-linux-gnu', root / 'usr/lib/x86_64-linux-gnu/pulseaudio', modules))
        self.env.update(LIBGL_ALWAYS_SOFTWARE='1', PULSE_SERVER='unix:' + str(self.run_directory / 'pulse-socket'))
        self.env.setdefault('LP_NUM_THREADS', '2'); self.env.setdefault('MESA_GLTHREAD', 'false')
        pulse = self.start([str(root / 'usr/bin/pulseaudio'), '-n', '--daemonize=no',
            '--exit-idle-time=-1', '--log-target=stderr', '--dl-search-path=' + str(modules),
            '--load=module-null-sink sink_name=decraft', '--load=module-native-protocol-unix socket=' +
            str(self.run_directory / 'pulse-socket') + ' auth-anonymous=1'], 'pulse.log')
        deadline = time.monotonic() + 5
        while not (self.run_directory / 'pulse-socket').exists() and pulse.poll() is None and time.monotonic() < deadline:
            time.sleep(.1)
        audio = subprocess.run([str(root / 'usr/bin/pactl'), 'list', 'short', 'sinks'], env=self.env,
                               capture_output=True, text=True, timeout=5)
        if audio.returncode or 'decraft' not in audio.stdout:
            raise RuntimeError('Virtual audio failed; see pulse.log')
        self.result['virtual_audio_ready'] = True
        readfd, writefd = os.pipe()
        try:
            self.start([str(root / 'usr/bin/Xvfb'), '-displayfd', str(writefd), '-screen', '0',
                        '1280x720x24', '-nolisten', 'tcp'], 'xvfb.log', pass_fds=(writefd,))
            os.close(writefd); writefd = None
            if not select.select([readfd], [], [], 5)[0]:
                raise RuntimeError('Virtual display did not initialize')
            number = os.read(readfd, 64).strip().decode()
            if not number.isdigit():
                raise RuntimeError('Invalid virtual display')
            self.env['DISPLAY'] = ':' + number
        finally:
            os.close(readfd)
            if writefd is not None: os.close(writefd)
        self.result['display'] = self.env['DISPLAY']

    def runtime(self):
        errors = (self.run_directory / 'runtime-stderr.log').open('w'); self.streams.append(errors)
        self.server = subprocess.Popen([sys.executable, str(PROJECT / 'tools/fusion.py'), 'serve',
            '--port', str(self.port), '--database', str(self.database)], env=self.env,
            stdout=subprocess.PIPE, stderr=errors, text=True)
        self.processes.append(self.server)
        ready = queue.Queue(maxsize=1)
        def read_output():
            with (self.run_directory / 'runtime-stdout.log').open('w') as log:
                first = self.server.stdout.readline(); log.write(first); log.flush()
                ready.put(first)
                for line in self.server.stdout: log.write(line); log.flush()
        self.reader = threading.Thread(target=read_output, daemon=True); self.reader.start()
        try:
            line = ready.get(timeout=15)
        except queue.Empty:
            raise RuntimeError('Shared runtime did not initialize; see runtime-stderr.log') from None
        if not line or self.server.poll() is not None:
            raise RuntimeError('Shared runtime startup failed; see runtime-stderr.log')
        self.endpoint = json.loads(line)['endpoint']
        with urllib.request.urlopen(self.endpoint + '/v1/status', timeout=5) as response:
            state = json.load(response)
        if state['abi_version'] != 1 or len(state['modules']) != 7:
            raise RuntimeError('Compiled runtime ABI or registered modules are incompatible')
        self.first_event = event_summary(self.database)['last_id']
        self.result.update(runtime_endpoint=self.endpoint, runtime_pid=self.server.pid,
                           first_event_id=self.first_event,
                           compiled_modules=[m['id'] for m in state['modules']])

    def run(self, seconds=None, require_ticks=False):
        try:
            validate_config(self.config)
            working = Path(self.config['game_directory']).resolve()
            self.lock = HostLock(working)
            self.result['bridge'] = install_bridge(working)
            self.display(); self.runtime()
            command = [self.config['java'], '-Xms1G', '-Xmx5G', '-Dsun.zip.disableMemoryMapping=true',
                '-Djava.library.path=' + self.config['natives'],
                '-Dorg.lwjgl.opengl.Display.allowSoftwareOpenGL=true', '-Dfml.queryResult=confirm',
                '-Ddecraft.bridge.url=' + self.endpoint + '/v1/events',
                '-cp', os.pathsep.join(self.config['classpath']), self.config['main_class']]
            if self.config.get('prefer_ipv4_stack', False):
                command.insert(1, '-Djava.net.preferIPv4Stack=true')
            self.client = self.start(command + self.config['arguments'], 'minecraft.log', cwd=working)
            self.result.update(client_pid=self.client.pid, diagnostic_only=self.config.get('diagnostic_only', False))
            self.result['status'] = 'running'
            (self.run_directory / 'launch.json').write_text(json.dumps(self.result, indent=2) + '\n')
            print(json.dumps(self.result), flush=True)
            deadline = time.monotonic() + seconds if seconds is not None else None
            capture = 0
            while self.client.poll() is None:
                if self.server.poll() is not None:
                    raise RuntimeError('Shared runtime exited while the game was running')
                if deadline is not None and time.monotonic() >= deadline:
                    self.result['status'] = 'diagnostic_timeout'; break
                if self.virtual_display and time.monotonic() >= capture:
                    active = {'run': str(self.run_directory), 'display': self.env['DISPLAY'],
                              'pid': self.client.pid, 'forge': True, 'combined': True}
                    (self.logs / 'active-baseline.json').write_text(json.dumps(active))
                    subprocess.run(['import', '-display', self.env['DISPLAY'], '-window', 'root',
                                    str(self.run_directory / 'live.png')], capture_output=True, timeout=8)
                    capture = time.monotonic() + 30
                time.sleep(.2)
            self.result['client_exit_code'] = self.client.poll()
            events = event_summary(self.database, self.first_event)
            self.result['bridge_events'] = events
            if self.result['status'] == 'running':
                self.result['status'] = ('client_failed' if self.client.returncode else
                    'passed_host_bridge' if events['recent_modpack_ticks'] else 'client_exited_without_world_ticks')
            return 0 if self.client.returncode == 0 and (not require_ticks or events['recent_modpack_ticks']) else 2
        except KeyboardInterrupt:
            self.result['status'] = 'interrupted'; return 130
        except (OSError, ValueError, RuntimeError, KeyError, StopIteration, subprocess.TimeoutExpired) as error:
            self.result.update(status='launch_failed', error=str(error)); return 1
        finally:
            # The game shuts down before its runtime. Existing worlds, mods and
            # SQLite sessions stay in place for the next launch.
            for process in reversed(self.processes):
                if process.poll() is None:
                    process.terminate()
                    try: process.wait(timeout=15 if process is self.client else 5)
                    except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
            if self.reader is not None: self.reader.join(timeout=2)
            if self.server is not None and self.server.stdout is not None: self.server.stdout.close()
            for stream in self.streams: stream.close()
            if self.lock is not None: self.lock.close()
            active = self.logs / 'active-baseline.json'
            if active.exists() and json.loads(active.read_text()).get('run') == str(self.run_directory): active.unlink()
            self.result['owned_processes_stopped'] = all(p.poll() is not None for p in self.processes)
            self.result['scope'] = 'Original modpack host plus shared source runtime and tick transport; crossover gameplay incomplete.'
            (self.run_directory / 'result.json').write_text(json.dumps(self.result, indent=2) + '\n')
            print(json.dumps(self.result), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('/workspace/runtime-tools/forge-launch.json'))
    parser.add_argument('--database', type=Path, default=PROJECT / 'runtime/fusion.sqlite3')
    parser.add_argument('--logs', type=Path, default=PROJECT / 'runtime/logs')
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--virtual-display', action='store_true')
    parser.add_argument('--seconds', type=int, help='Bounded cloud diagnostic; normal launches run until the game exits')
    parser.add_argument('--require-ticks', action='store_true', help='Diagnostic fails unless a world sends actual bridge events')
    args = parser.parse_args()
    if not 0 <= args.port <= 65535: parser.error('Port must be 0..65535')
    if args.seconds is not None and not 1 <= args.seconds <= 1800: parser.error('Diagnostic duration must be 1..1800 seconds')
    config = load_config(args.config)
    return CombinedLaunch(config, args.database, args.logs, args.port, args.virtual_display).run(args.seconds, args.require_ticks)


if __name__ == '__main__':
    sys.exit(main())
