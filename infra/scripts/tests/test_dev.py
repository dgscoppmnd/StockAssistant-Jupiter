import importlib.util
import json
import os
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("dev", Path(__file__).resolve().parents[1] / "dev.py")
assert SPEC is not None and SPEC.loader is not None
dev = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dev)
REGISTRY = "118645514410.dkr.ecr.eu-west-1.amazonaws.com"


class DockerConfigTests(unittest.TestCase):
    def test_helper_selection(self):
        cases = [
            ({}, False),
            ({"credsStore": "desktop", "credHelpers": None}, False),
            ({"credsStore": "ecr-login"}, True),
            ({"credsStore": "desktop", "credHelpers": {REGISTRY: "ecr-login"}}, True),
            ({"credsStore": "ecr-login", "credHelpers": {REGISTRY: "desktop"}}, False),
        ]
        with TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"DOCKER_CONFIG": directory}):
                self.assertFalse(dev.uses_ecr_helper(REGISTRY))
                for config, expected in cases:
                    with self.subTest(config=config):
                        (Path(directory) / "config.json").write_text(json.dumps(config), encoding="utf-8")
                        self.assertEqual(dev.uses_ecr_helper(REGISTRY), expected)

    def test_invalid_config_stops_deployment(self):
        with TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"DOCKER_CONFIG": directory}):
                for contents in ("{", "[]", '{"credHelpers": ["ecr-login"]}'):
                    with self.subTest(contents=contents):
                        (Path(directory) / "config.json").write_text(contents, encoding="utf-8")
                        with self.assertRaises(SystemExit):
                            dev.uses_ecr_helper(REGISTRY)


class HelperEnvironmentTests(unittest.TestCase):
    def test_exports_only_to_child_environment(self):
        credentials = {"AccessKeyId": "test-id", "SecretAccessKey": "test-secret", "SessionToken": "test-token"}
        result = subprocess.CompletedProcess([], 0, json.dumps(credentials), "")
        with patch.dict(os.environ, {"AWS_SESSION_TOKEN": "old-token"}):
            with patch.object(dev.shutil, "which", return_value="helper"):
                with patch.object(dev.subprocess, "run", return_value=result) as run:
                    env = dev.ecr_helper_environment()
        self.assertEqual(env["AWS_ACCESS_KEY_ID"], "test-id")
        self.assertEqual(env["AWS_SECRET_ACCESS_KEY"], "test-secret")
        self.assertEqual(env["AWS_SESSION_TOKEN"], "test-token")
        self.assertEqual(env["AWS_ECR_DISABLE_CACHE"], "true")
        self.assertEqual(env["AWS_REGION"], dev.REGION)
        self.assertEqual(env["AWS_DEFAULT_REGION"], dev.REGION)
        run.assert_called_once_with(
            ["aws", "configure", "export-credentials", "--format", "process"],
            capture_output=True, text=True,
        )

    def test_no_session_token_does_not_reuse_inherited_token(self):
        credentials = {"AccessKeyId": "test-id", "SecretAccessKey": "test-secret"}
        result = subprocess.CompletedProcess([], 0, json.dumps(credentials), "")
        with patch.dict(os.environ, {"AWS_SESSION_TOKEN": "old", "AWS_SECURITY_TOKEN": "old"}):
            with patch.object(dev.shutil, "which", return_value="helper"):
                with patch.object(dev.subprocess, "run", return_value=result):
                    env = dev.ecr_helper_environment()
            self.assertEqual(os.environ["AWS_SESSION_TOKEN"], "old")
        self.assertNotIn("AWS_SESSION_TOKEN", env)
        self.assertNotIn("AWS_SECURITY_TOKEN", env)

    def test_missing_helper_stops_before_export(self):
        with patch.object(dev.shutil, "which", return_value=None):
            with patch.object(dev.subprocess, "run") as run:
                with self.assertRaises(SystemExit):
                    dev.ecr_helper_environment()
                run.assert_not_called()

    def test_invalid_export_stops_without_exposing_output(self):
        results = [
            subprocess.CompletedProcess([], 1, "", "sensitive-output"),
            subprocess.CompletedProcess([], 0, "sensitive-output", ""),
            subprocess.CompletedProcess([], 0, "[]", ""),
            subprocess.CompletedProcess([], 0, "{}", ""),
            subprocess.CompletedProcess([], 0, '{"AccessKeyId": 123}', ""),
        ]
        with patch.object(dev.shutil, "which", return_value="helper"):
            for result in results:
                with self.subTest(result=result):
                    with patch.object(dev.subprocess, "run", return_value=result):
                        with self.assertRaises(SystemExit) as error:
                            dev.ecr_helper_environment()
                        self.assertNotIn("sensitive-output", str(error.exception))


class DeployBackendTests(unittest.TestCase):
    def test_helper_skips_login_and_passes_environment(self):
        env = {"AWS_ACCESS_KEY_ID": "test-id"}
        with patch.object(dev, "account", return_value="118645514410"):
            with patch.object(dev, "uses_ecr_helper", return_value=True):
                with patch.object(dev, "ecr_helper_environment", return_value=env):
                    with patch.object(dev, "aws") as aws, patch.object(dev, "run") as run:
                        with patch.object(dev.subprocess, "run") as subprocess_run:
                            dev.deploy_backend("test")
        aws.assert_not_called()
        subprocess_run.assert_not_called()
        self.assertEqual(run.call_count, 3)
        build = run.call_args_list[0]
        self.assertEqual(build.args[0][:3], ["docker", "buildx", "build"])
        self.assertIs(build.kwargs["env"], env)
        self.assertIn("--push", build.args[0])
        self.assertEqual(run.call_args_list[1].args[0][1], "lambda")
        self.assertEqual(run.call_args_list[2].args[0][1:3], ["lambda", "wait"])

    def test_no_helper_preserves_password_stdin_login(self):
        with patch.object(dev, "account", return_value="118645514410"):
            with patch.object(dev, "uses_ecr_helper", return_value=False):
                with patch.object(dev, "aws", return_value="test-password") as aws:
                    with patch.object(dev, "run"), patch.object(dev.subprocess, "run") as login:
                        dev.deploy_backend("test")
        aws.assert_called_once_with("ecr", "get-login-password")
        login.assert_called_once_with(
            ["docker", "login", "--username", "AWS", "--password-stdin", REGISTRY],
            input="test-password", text=True, check=True,
        )

    def test_build_failure_never_updates_lambda(self):
        with patch.object(dev, "account", return_value="118645514410"):
            with patch.object(dev, "uses_ecr_helper", return_value=True):
                with patch.object(dev, "ecr_helper_environment", return_value={}):
                    with patch.object(dev, "run", side_effect=SystemExit("build failed")) as run:
                        with self.assertRaises(SystemExit):
                            dev.deploy_backend("test")
        run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
