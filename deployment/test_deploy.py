"""Exercise deployment ordering and recovery without touching Docker or a server."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


TAG = "canary-20261013-abcdef-123-1"
PREVIOUS = "canary-previous"
SOURCE = Path(__file__).with_name("deploy.sh")


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        (self.root / "db").mkdir()
        (self.root / "db" / "evidence.txt").write_text("preserved evidence")
        self.original_env = f"TAG={PREVIOUS}\nDOMAIN=example.com\nSECRET=keep-me\n"
        (self.root / ".env").write_text(self.original_env)
        (self.root / "compose.yml").write_text("old compose")
        (self.root / "Caddyfile").write_text("old caddy")
        release = self.root / "releases" / TAG
        release.mkdir(parents=True)
        (release / "compose.yml").write_text("new compose")
        (release / "Caddyfile").write_text("new caddy")
        self.script = self.root / "deploy.sh"
        self.script.write_text(SOURCE.read_text().replace("/opt/ciso", str(self.root)))
        self.log = self.root / "calls.jsonl"
        self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}",
                        TEST_ROOT=str(self.root), TEST_LOG=str(self.log), TEST_FAIL="")
        docker = self.bin / "docker"
        docker.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
a = sys.argv[1:]
root = pathlib.Path(os.environ["TEST_ROOT"])
with open(os.environ["TEST_LOG"], "a") as f:
    f.write(json.dumps({"args": a, "config": os.environ.get("DOCKER_CONFIG")}) + "\\n")
joined = " ".join(a)
failure = os.environ["TEST_FAIL"]
phase = ("login" if a[0] == "login" else
         "pull" if "pull" in a else
         "backup" if "pg_dump" in joined else
         "migration" if "migrate --noinput" in joined else
         "startup" if a[:2] == ["compose", "up"] else "")
if failure and phase == failure:
    sys.exit(1)
if phase == "login":
    sys.stdin.read()
if phase == "backup":
    print("fake postgres custom dump")
if "pg_restore" in a:
    sys.stdin.read()
if phase == "migration":
    assert list((root / "backups").glob("*/complete")), "migration before backup"
''')
        docker.chmod(0o755)
        for name, body in {
            "flock": "exit 0",
            "curl": '[ "$TEST_FAIL" != health ]',
        }.items():
            program = self.bin / name
            program.write_text(f"#!/bin/sh\n{body}\n")
            program.chmod(0o755)

    def run_deploy(self, failure="", tag=TAG):
        self.env["TEST_FAIL"] = failure
        result = subprocess.run(["bash", str(self.script), tag, "github-actions[bot]"],
                                input="temporary-token\n", text=True,
                                capture_output=True, env=self.env)
        self.calls = [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
        self.assertNotIn("temporary-token", result.stdout + result.stderr)
        for call in self.calls:
            self.assertFalse(Path(call["config"]).exists(), "registry credentials not removed")
        return result

    def commands(self):
        return [call["args"] for call in self.calls]

    def test_success_preserves_secrets_and_creates_matching_backup(self):
        result = self.run_deploy()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "deployed-tag").read_text().strip(), TAG)
        self.assertEqual((self.root / ".env").read_text(), self.original_env.replace(PREVIOUS, TAG))
        backup, = (self.root / "backups").iterdir()
        self.assertEqual((backup / ".env").read_text(), self.original_env)
        self.assertTrue((backup / "complete").exists())
        self.assertTrue((backup / "uploads.tar.gz").exists())
        self.assertEqual((self.root / "compose.yml").read_text(), "new compose")
        self.assertTrue(any("--force-recreate" in command for command in self.commands()))

    def test_pull_failure_leaves_old_app_running(self):
        result = self.run_deploy("pull")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(command[:2] == ["compose", "stop"] for command in self.commands()))
        self.assertEqual((self.root / ".env").read_text(), self.original_env)

    def test_backup_failure_resumes_old_app_without_migrating(self):
        result = self.run_deploy("backup")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(["compose", "start"], self.commands())
        self.assertFalse(any("migrate" in command for command in self.commands()))
        self.assertEqual((self.root / ".env").read_text(), self.original_env)

    def test_migration_failure_does_not_start_or_revert_app(self):
        result = self.run_deploy("migration")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(["compose", "start"], self.commands())
        self.assertFalse(any(command[:2] == ["compose", "up"] for command in self.commands()))
        self.assertFalse((self.root / "deployed-tag").exists())

    def test_unhealthy_release_is_not_reported_as_success(self):
        for failure in ("startup", "health"):
            with self.subTest(failure=failure):
                result = self.run_deploy(failure)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(["compose", "start"], self.commands())
                self.assertFalse((self.root / "deployed-tag").exists())

    def test_invalid_tag_cannot_execute_commands(self):
        result = self.run_deploy(tag="canary-$(touch pwned)")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.calls)


if __name__ == "__main__":
    unittest.main()
