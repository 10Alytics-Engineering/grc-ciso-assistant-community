#!/usr/bin/env python3
"""Switch between healthy web slots without stopping the public proxy."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import signal
import sqlite3
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path('/opt/ciso')
REPOSITORY = 'ghcr.io/10alytics-engineering/grc-ciso-assistant-community'
PROXY = 'grc-caddy-1'


class Deployment:
    def __init__(self, root, tag, user, loaded_images=False):
        if not re.fullmatch(r'canary-[a-zA-Z0-9-]+', tag):
            raise ValueError('Invalid release tag')
        if not re.fullmatch(r'[a-zA-Z0-9_-]+(?:\[bot\])?', user):
            raise ValueError('Invalid registry username')
        self.root, self.tag, self.user = Path(root), tag, user
        self.loaded_images = loaded_images
        self.release = self.root / 'releases' / tag
        self.env = os.environ.copy()
        self.original_env = (self.root / '.env').read_text()
        self.domain = self.env_value('DOMAIN')
        if not re.fullmatch(r'[a-zA-Z0-9.-]+', self.domain):
            raise ValueError('Invalid domain')
        self.state_file = self.root / 'deployment-state.json'
        self.original_state = self.state_file.read_text() if self.state_file.exists() else None
        self.active = json.loads(self.original_state) if self.original_state else {
            'slot': 'legacy', 'tag': self.env_value('TAG')}
        if self.active['slot'] not in ('legacy', 'blue', 'green'):
            raise ValueError('Invalid active slot')
        self.slot = 'green' if self.active['slot'] == 'blue' else 'blue'
        self.slot_dir = self.root / 'slots' / self.slot
        self.old_caddy = (self.root / 'Caddyfile').read_text()
        if not self.original_state and re.search(r'backend-(blue|green)', self.old_caddy):
            raise RuntimeError('Proxy uses a slot but deployment-state.json is missing; inspect before deploying')
        self.old_worker = 'grc-huey-1' if self.active['slot'] == 'legacy' else f"grc-{self.active['slot']}-huey-1"
        self.new_worker = f'grc-{self.slot}-huey-1'
        self.route_attempted = self.worker_changed = self.candidate_started = False

    def env_value(self, key):
        match = re.search(rf'^{key}=(.+)$', self.original_env, re.MULTILINE)
        if not match:
            raise ValueError(f'{key} missing in server .env')
        return match[1]

    def cmd(self, *args, **kwargs):
        return subprocess.run([str(a) for a in args], check=True, env=self.env, **kwargs)

    def compose(self, *args, **kwargs):
        env = dict(self.env, TAG=self.tag, SLOT=self.slot)
        return subprocess.run([
            'docker', 'compose', '-p', f'grc-{self.slot}', '--project-directory', str(self.root),
            '--env-file', str(self.root / '.env'), '-f', str(self.slot_dir / 'compose.yml'),
            *args], check=True, env=env, **kwargs)

    def atomic_write(self, path, content):
        temporary = path.with_name(path.name + '.next')
        temporary.write_text(content)
        temporary.replace(path)

    def public_check(self, tag, require_header=True):
        for path in ('/api/health/', '/login'):
            for attempt in range(12):
                try:
                    request = urllib.request.Request(f'https://{self.domain}{path}',
                                                     headers={'Cache-Control': 'no-cache'})
                    with urllib.request.urlopen(request, timeout=15) as response:
                        if response.status != 200:
                            raise RuntimeError(f'{path} is not healthy')
                        if require_header and response.headers.get('X-GRC-Release') != tag:
                            raise RuntimeError(f'{path} is not serving release {tag}')
                        response.read()
                    break
                except Exception:
                    if attempt == 11:
                        raise
                    time.sleep(2)

    def backup(self):
        print('Taking online database, upload and queue backups.', flush=True)
        backup = self.root / 'backups' / f"auto-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{self.tag}"
        backup.mkdir(parents=True, mode=0o700, exist_ok=False)
        for name in ('.env', 'compose.yml', 'Caddyfile', 'deployment-state.json'):
            if (self.root / name).exists():
                shutil.copy2(self.root / name, backup / name)
        with (backup / 'database.dump').open('wb') as output:
            self.cmd('docker', 'run', '--rm', '--env-file', self.root / '.env',
                     '-v', f'{self.root}/db:/code/db:ro', 'postgres:17', 'sh', '-ec',
                     'export PGPASSWORD="$POSTGRES_PASSWORD" PGSSLMODE="$POSTGRES_SSL_MODE"; '
                     'exec pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$POSTGRES_USER" '
                     '-d "$POSTGRES_NAME" --format=custom --no-owner --no-acl --lock-wait-timeout=10s',
                     stdout=output)
        if not (backup / 'database.dump').stat().st_size:
            raise RuntimeError('Empty database backup')
        with (backup / 'database.dump').open('rb') as source:
            self.cmd('docker', 'run', '--rm', '-i', 'postgres:17', 'pg_restore', '--list',
                     stdin=source, stdout=subprocess.DEVNULL)
        # Retry if uploads change while tar reads them; never stop HTTP writers.
        for attempt in range(3):
            try:
                self.cmd('tar', '--exclude=db/huey.db*', '-czf', backup / 'uploads.tar.gz',
                         '-C', self.root, 'db')
                break
            except subprocess.CalledProcessError as error:
                if error.returncode != 1 or attempt == 2:
                    raise
        self.cmd('tar', '-tzf', backup / 'uploads.tar.gz', stdout=subprocess.DEVNULL)
        queue = self.root / 'db' / 'huey.db'
        if queue.exists():
            with sqlite3.connect(f'file:{queue}?mode=ro', uri=True) as source:
                with sqlite3.connect(backup / 'huey.db') as destination:
                    source.backup(destination)
        (backup / 'complete').touch()
        print(f'Online backup saved: {backup}', flush=True)

    def preserve_assets(self, container, name):
        assets = self.release / f'assets-{name}'
        assets.mkdir(exist_ok=True)
        self.cmd('docker', 'cp', f'{container}:/app/build/client/_app/immutable/.', str(assets))
        self.cmd('docker', 'exec', PROXY, 'mkdir', '-p', '/data/grc-assets/_app/immutable')
        self.cmd('docker', 'cp', f'{assets}/.', f'{PROXY}:/data/grc-assets/_app/immutable/')
        shutil.rmtree(assets)

    def reload_proxy(self, config):
        # Preserve the inode of the existing bind mount. Replacing this file
        # atomically would leave the running container reading the old inode.
        (self.root / 'Caddyfile').write_text(config)
        self.cmd('docker', 'exec', PROXY, 'caddy', 'reload', '--config', '/etc/caddy/Caddyfile')
        (self.root / 'last-switch-time').write_text(str(time.time()))

    def drain_worker(self, container):
        exists = self.cmd('docker', 'ps', '-aq', '--filter', f'name=^/{container}$',
                          capture_output=True, text=True).stdout.strip()
        if not exists:
            return
        self.cmd('docker', 'update', '--restart=no', container)
        status = self.cmd('docker', 'inspect', '--format', '{{.State.Running}}', container,
                          capture_output=True, text=True).stdout.strip()
        if status == 'true':
            # Legacy images use a shell as PID 1. Signal the actual consumer,
            # allowing in-flight jobs to finish instead of sending SIGTERM.
            self.cmd('docker', 'exec', container, 'python', '-c',
                     "import os,pathlib,signal\n"
                     "for p in pathlib.Path('/proc').iterdir():\n"
                     " if not p.name.isdigit(): continue\n"
                     " try:\n"
                     "  if b'run_huey' in (p/'cmdline').read_bytes().split(b'\\0'):\n"
                     "   os.kill(int(p.name),signal.SIGINT)\n"
                     " except (FileNotFoundError,ProcessLookupError): pass\n")
            self.cmd('docker', 'wait', container, timeout=300)

    def rollback(self):
        print('Deployment failed; restoring the previous route and worker.', flush=True)
        if self.route_attempted:
            self.reload_proxy(self.old_caddy)
        if self.worker_changed:
            self.drain_worker(self.new_worker)
            self.cmd('docker', 'update', '--restart=unless-stopped', self.old_worker)
            self.cmd('docker', 'start', self.old_worker)
        self.atomic_write(self.root / '.env', self.original_env)
        if self.original_state is None:
            self.state_file.unlink(missing_ok=True)
        else:
            self.atomic_write(self.state_file, self.original_state)
        self.atomic_write(self.root / 'deployed-tag', self.active['tag'] + '\n')
        # After a proxy switch keep both web slots alive to finish requests.
        if self.candidate_started and not self.route_attempted:
            self.compose('down', '--timeout', '120')

    def run(self):
        self.public_check(self.active['tag'], require_header=self.active['slot'] != 'legacy')
        if not self.loaded_images:
            self.cmd('docker', 'login', 'ghcr.io', '--username', self.user, '--password-stdin')
        # The previous slot remains alive after cutover. Do not recycle it until
        # all requests within our five-minute drain window have had time to finish.
        last_switch = self.root / 'last-switch-time'
        if last_switch.exists():
            delay = max(0, 300 - (time.time() - float(last_switch.read_text())))
            if delay:
                print(f'Allowing the previous slot to drain for {delay:.0f}s.', flush=True)
                time.sleep(delay)
        if self.active['slot'] != 'legacy':
            # The first conversion leaves the legacy web containers draining.
            # Retire them on the next release, without touching their proxy.
            for service in ('backend', 'frontend', 'huey'):
                container = f'grc-{service}-1'
                exists = self.cmd('docker', 'ps', '-aq', '--filter', f'name=^/{container}$',
                                  capture_output=True, text=True).stdout.strip()
                if exists:
                    self.cmd('docker', 'stop', '--time', '120', container)
                    self.cmd('docker', 'rm', container)
        self.slot_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.release / 'compose.slot.yml', self.slot_dir / 'compose.yml')
        self.compose('config', '--quiet')
        if self.loaded_images:
            for component in ('backend', 'frontend'):
                self.cmd('docker', 'image', 'inspect', f'{REPOSITORY}/{component}:{self.tag}',
                         stdout=subprocess.DEVNULL)
        else:
            self.compose('pull')
            self.cmd('docker', 'pull', 'postgres:17')
        self.compose('down', '--timeout', '120')
        # Never apply migrations under live traffic. A schema change needs a
        # separately reviewed expand/contract migration before this release.
        print('Checking that this release needs no database migrations.', flush=True)
        self.compose('run', '--rm', '--no-deps', '--entrypoint', 'python', 'backend',
                     'manage.py', 'migrate', '--check')
        self.backup()
        try:
            self.compose('run', '--rm', '--no-deps', '--entrypoint', 'python', 'backend',
                         'manage.py', 'storelibraries')
            self.candidate_started = True
            self.compose('up', '-d', '--pull', 'never', '--wait', '--wait-timeout', '300',
                         'backend', 'frontend')
            for service in ('backend', 'frontend'):
                self.cmd('docker', 'network', 'connect', '--alias', f'{service}-{self.slot}',
                         'grc_default', f'grc-{self.slot}-{service}-1')
            for host, path in ((f'backend-{self.slot}:8000', '/api/health/'),
                               (f'frontend-{self.slot}:3000', '/login')):
                self.cmd('docker', 'exec', PROXY, 'wget', '-q', '-O', '/dev/null',
                         '--header', f'Host: {self.domain}', '--header', 'X-Forwarded-Proto: https',
                         f'http://{host}{path}')
            old_frontend = 'grc-frontend-1' if self.active['slot'] == 'legacy' else f"grc-{self.active['slot']}-frontend-1"
            self.preserve_assets(old_frontend, 'previous')
            self.preserve_assets(f'grc-{self.slot}-frontend-1', 'candidate')
            config = (self.release / 'Caddyfile.slot').read_text().replace('__SLOT__', self.slot).replace('__RELEASE__', self.tag)
            candidate_config = self.release / 'Caddyfile.candidate'
            candidate_config.write_text(config)
            self.cmd('docker', 'cp', candidate_config, f'{PROXY}:/tmp/Caddyfile.candidate')
            self.cmd('docker', 'exec', PROXY, 'caddy', 'validate', '--config', '/tmp/Caddyfile.candidate')
            # Validate the new consumer before stopping the current one.
            self.compose('run', '--rm', '--no-deps', '--entrypoint', 'python', 'huey',
                         '-c', 'import django; django.setup(); from huey.contrib.djhuey import HUEY; HUEY.pending_count()')
            self.worker_changed = True
            self.drain_worker(self.old_worker)
            self.compose('up', '-d', '--no-deps', '--pull', 'never', '--wait', '--wait-timeout', '180', 'huey')
            self.route_attempted = True
            self.reload_proxy(config)
            self.public_check(self.tag)
            self.atomic_write(self.root / '.env', re.sub(r'^TAG=.*$', f'TAG={self.tag}', self.original_env, flags=re.MULTILINE))
            self.atomic_write(self.state_file, json.dumps({'slot': self.slot, 'tag': self.tag,
                              'previous_slot': self.active['slot'], 'previous_tag': self.active['tag']}) + '\n')
            self.atomic_write(self.root / 'deployed-tag', self.tag + '\n')
        except BaseException:
            self.rollback()
            raise
        print(f'Healthy release {self.tag} is serving from {self.slot}; previous web slot remains running.', flush=True)
        # Only complete backups count toward retention. Failed attempts must not
        # evict usable recovery points. Never prune either running web image.
        backups = sorted((p for p in (self.root / 'backups').glob('auto-*') if (p / 'complete').exists()), reverse=True)
        for backup in backups[7:]:
            shutil.rmtree(backup)
        for component in ('frontend', 'backend'):
            repository = f'{REPOSITORY}/{component}'
            tags = self.cmd('docker', 'image', 'ls', repository, '--format', '{{.Tag}}',
                            capture_output=True, text=True).stdout.splitlines()
            for tag in tags:
                if tag.startswith('canary-') and tag not in (self.tag, self.active['tag']):
                    try:
                        self.cmd('docker', 'image', 'rm', f'{repository}:{tag}')
                    except subprocess.CalledProcessError:
                        print(f'Image still in use; retaining {repository}:{tag}', flush=True)


def interrupted(signum, frame):
    raise InterruptedError(f'Deployment interrupted by signal {signum}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('tag')
    parser.add_argument('registry_user')
    parser.add_argument('--loaded-images', action='store_true', help='Use already loaded images for an operator-run rehearsal')
    args = parser.parse_args()
    os.umask(0o077)
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGHUP, interrupted)
    with (ROOT / 'deploy.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with tempfile.TemporaryDirectory(prefix='grc-registry-') as credentials:
            deployment = Deployment(ROOT, args.tag, args.registry_user, args.loaded_images)
            deployment.env['DOCKER_CONFIG'] = credentials
            deployment.run()


if __name__ == '__main__':
    main()
