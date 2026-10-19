import os
import unittest
from unittest.mock import patch

import secrets_loader


class SecretsLoaderTests(unittest.TestCase):
    def test_loads_serpapi_with_decryption(self):
        environment = {
            "AWS_LAMBDA_FUNCTION_NAME": "test-function",
            "SECRETS_FROM_SSM": "true",
            "AWS_REGION": "eu-west-1",
            **{name: "already-configured" for name in secrets_loader.SECRET_PARAMETERS},
            "SERPAPI_API_KEY": "",
        }
        with patch.dict(os.environ, environment, clear=True), patch("boto3.client") as client:
            client.return_value.get_parameters.return_value = {
                "Parameters": [{
                    "Name": "/stockassistant/prod/serpapi_api_key",
                    "Value": "test-only-key",
                }]
            }
            secrets_loader.load_secrets_from_ssm()
            self.assertEqual(os.environ["SERPAPI_API_KEY"], "test-only-key")
            client.return_value.get_parameters.assert_called_once_with(
                Names=["/stockassistant/prod/serpapi_api_key"], WithDecryption=True
            )
            self.assertEqual(os.environ["OPENAI_API_KEY"], "already-configured")

    def test_does_not_overwrite_existing_secrets(self):
        environment = {
            "AWS_LAMBDA_FUNCTION_NAME": "test-function",
            "SECRETS_FROM_SSM": "true",
            **{name: "already-configured" for name in secrets_loader.SECRET_PARAMETERS},
        }
        with patch.dict(os.environ, environment, clear=True), patch("boto3.client") as client:
            secrets_loader.load_secrets_from_ssm()
            client.assert_not_called()
            self.assertEqual(os.environ["SERPAPI_API_KEY"], "already-configured")

    def test_local_does_not_read_ssm(self):
        with patch.dict(os.environ, {}, clear=True), patch("boto3.client") as client:
            secrets_loader.load_secrets_from_ssm()
            client.assert_not_called()

    def test_missing_parameter_fails_explicitly(self):
        with patch.dict(os.environ, {
            "AWS_LAMBDA_FUNCTION_NAME": "test-function",
            "SECRETS_FROM_SSM": "true",
        }, clear=True), patch("boto3.client") as client:
            client.return_value.get_parameters.return_value = {
                "InvalidParameters": ["/stockassistant/prod/serpapi_api_key"]
            }
            with self.assertRaisesRegex(RuntimeError, "serpapi_api_key"):
                secrets_loader.load_secrets_from_ssm()
            self.assertNotIn("SERPAPI_API_KEY", os.environ)


if __name__ == "__main__":
    unittest.main()
