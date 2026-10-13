"""Test release ordering and rollback with simulated Docker and HTTP endpoints."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('grc_deploy', Path(__file__).with_name('deploy.py'))
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)
TAG = 'canary-new-123-1'
OLD = 'canary-previous-122-1'


class SimulatedDeployment(deploy.Deployment):
    def __init__(self, root, failure=''):
        super().__init__(root, TAG, 'github-actions[bot]', loaded_images=True)
        self.failure = failure
        self.events = []
        self.serving = self.active['slot']
        self.web = {self.serving: True, self.slot: False}
        self.workers = {self.old_worker: True}

    def fail(self, phase):
        if self.failure == phase:
            self.failure = ''
            raise subprocess.CalledProcessError(1, phase)

    def cmd(self, *args, **kwargs):
        args = [str(a) for a in args]
        self.events.append(args)
        output = ''
        if args[:3] == ['docker', 'ps', '-aq']:
            container = args[-1].removeprefix('name=^/').removesuffix('$')
            output = container if container in self.workers else ''
        elif args[:2] == ['docker', 'inspect']:
            output = 'true' if self.workers.get(args[-1]) else 'false'
        elif args[:2] == ['docker', 'wait']:
            if self.failure == 'drain':
                self.failure = ''
                raise subprocess.TimeoutExpired(args, 300)
            self.workers[args[-1]] = False
        elif args[:2] == ['docker', 'start']:
            self.workers[args[-1]] = True
        elif args[:4] == ['docker', 'exec', deploy.PROXY, 'caddy']:
            if 'validate' in args:
                self.fail('config')
            if 'reload' in args:
                self.fail('reload')
                config = (self.root / 'Caddyfile').read_text()
                self.serving = self.slot if f'backend-{self.slot}' in config else self.active['slot']
        elif args[:4] == ['docker', 'exec', deploy.PROXY, 'wget']:
            self.fail('readiness')
        # Every infrastructure operation must leave a web slot serving traffic.
        assert self.web[self.serving], f'traffic interrupted by {args}'
        return subprocess.CompletedProcess(args, 0, stdout=output)

    def compose(self, *args, **kwargs):
        args = list(args)
        self.events.append(['compose', *args])
        if 'migrate' in args:
            assert '--check' in args, 'automatic schema migration is forbidden'
            self.fail('migration')
        if args[0] == 'down':
            assert self.serving != self.slot, 'cannot remove the live slot'
            self.web[self.slot] = False
        if args[0] == 'up':
            if args[-1] == 'frontend':
                self.web[self.slot] = True
                self.fail('startup')
            elif args[-1] == 'huey':
                self.fail('worker-create')
                assert not self.workers[self.old_worker], 'duplicate schedulers'
                self.workers[self.new_worker] = True
                self.fail('worker-health')
        assert self.web[self.serving], f'traffic interrupted by {args}'
        return subprocess.CompletedProcess(args, 0, stdout='')

    def backup(self):
        self.events.append(['online-backup'])
        assert self.web[self.serving]
        self.fail('backup')
        (self.root / 'backups' / 'auto-current').mkdir(parents=True)
        (self.root / 'backups' / 'auto-current' / 'complete').touch()

    def preserve_assets(self, container, name):
        self.events.append(['preserve-assets', name])

    def public_check(self, tag, require_header=True):
        self.events.append(['public-check', tag])
        assert self.web[self.serving]
        if tag == TAG:
            assert self.serving == self.slot
            self.fail('public-health')


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.original_env = f'DOMAIN=example.com\nTAG={OLD}\nSECRET=keep-me\n'
        (self.root / '.env').write_text(self.original_env)
        (self.root / 'Caddyfile').write_text('reverse_proxy backend:8000')
        release = self.root / 'releases' / TAG
        release.mkdir(parents=True)
        (release / 'compose.slot.yml').write_text('slot compose fixture')
        (release / 'Caddyfile.slot').write_text('reverse_proxy backend-__SLOT__:8000\nrelease __RELEASE__')

    def test_legacy_conversion_preserves_http_and_hands_over_one_worker(self):
        deployment = SimulatedDeployment(self.root)
        deployment.run()
        self.assertEqual(deployment.serving, 'blue')
        self.assertTrue(deployment.web['legacy'])
        self.assertFalse(deployment.workers[deployment.old_worker])
        self.assertTrue(deployment.workers[deployment.new_worker])
        self.assertEqual(json.loads(deployment.state_file.read_text())['tag'], TAG)
        self.assertEqual((self.root / '.env').read_text(), self.original_env.replace(OLD, TAG))
        reload_index = next(i for i, args in enumerate(deployment.events) if 'reload' in args)
        for name in ('previous', 'candidate'):
            self.assertLess(deployment.events.index(['preserve-assets', name]), reload_index)
        self.assertFalse(any(args[:2] == ['docker', 'stop'] and deploy.PROXY in args for args in deployment.events))

    def test_next_release_uses_green_and_keeps_blue_available(self):
        (self.root / 'deployment-state.json').write_text(json.dumps({'slot': 'blue', 'tag': OLD}))
        (self.root / 'Caddyfile').write_text('reverse_proxy backend-blue:8000')
        deployment = SimulatedDeployment(self.root)
        deployment.run()
        self.assertEqual(deployment.serving, 'green')
        self.assertTrue(deployment.web['blue'])

    def test_pending_migration_or_backup_failure_leaves_live_services_untouched(self):
        for phase in ('migration', 'backup'):
            with self.subTest(phase=phase):
                deployment = SimulatedDeployment(self.root, phase)
                with self.assertRaises(subprocess.CalledProcessError):
                    deployment.run()
                self.assertEqual(deployment.serving, 'legacy')
                self.assertTrue(deployment.workers[deployment.old_worker])
                self.assertFalse(any('reload' in args for args in deployment.events))
                self.assertEqual((self.root / '.env').read_text(), self.original_env)

    def test_unready_candidate_does_not_switch_traffic_or_worker(self):
        for phase in ('startup', 'readiness', 'config'):
            with self.subTest(phase=phase):
                deployment = SimulatedDeployment(self.root, phase)
                # Each simulated run creates its own backup.
                backup = self.root / 'backups' / 'auto-current' / 'complete'
                if backup.exists():
                    backup.unlink()
                    backup.parent.rmdir()
                with self.assertRaises(subprocess.CalledProcessError):
                    deployment.run()
                self.assertEqual(deployment.serving, 'legacy')
                self.assertTrue(deployment.workers[deployment.old_worker])
                self.assertFalse(deployment.web[deployment.slot])

    def test_worker_creation_failure_restores_old_worker_even_without_new_container(self):
        deployment = SimulatedDeployment(self.root, 'worker-create')
        with self.assertRaises(subprocess.CalledProcessError):
            deployment.run()
        self.assertTrue(deployment.workers[deployment.old_worker])
        self.assertEqual(deployment.serving, 'legacy')

    def test_failure_after_switch_restores_route_and_worker_without_stopping_web(self):
        deployment = SimulatedDeployment(self.root, 'public-health')
        with self.assertRaises(subprocess.CalledProcessError):
            deployment.run()
        self.assertEqual(deployment.serving, 'legacy')
        self.assertTrue(deployment.web['blue'])
        self.assertTrue(deployment.workers[deployment.old_worker])
        self.assertFalse(deployment.workers[deployment.new_worker])
        self.assertFalse(deployment.state_file.exists())
        self.assertEqual((self.root / '.env').read_text(), self.original_env)

    def test_worker_drain_timeout_never_forcibly_kills_running_jobs(self):
        deployment = SimulatedDeployment(self.root, 'drain')
        with self.assertRaises(subprocess.TimeoutExpired):
            deployment.run()
        self.assertTrue(deployment.workers[deployment.old_worker])
        self.assertFalse(any(args[:2] in (['docker', 'kill'], ['docker', 'stop']) for args in deployment.events))

    def test_invalid_release_tag_is_rejected(self):
        with self.assertRaises(ValueError):
            deploy.Deployment(self.root, 'canary-$(touch pwned)', 'user')


if __name__ == '__main__':
    unittest.main()
