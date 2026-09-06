import os
import unittest
from unittest.mock import patch

from external_connectors import ExternalSourceError, SerpApiConnector, get_connectors


class ExternalConnectorTests(unittest.TestCase):
    def test_sources_are_unavailable_without_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            statuses = {name: connector.status().to_dict() for name, connector in get_connectors().items()}
        self.assertFalse(statuses["serpapi"]["available"])
        self.assertFalse(statuses["aliexpress"]["available"])
        self.assertFalse(statuses["amazon_sp_api"]["available"])

    def test_serpapi_does_not_issue_request_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            connector = SerpApiConnector()
            with self.assertRaises(ExternalSourceError):
                connector.shopping("robot", "ES", "es")

    def test_trends_uses_the_official_google_trends_engine(self):
        with patch.dict(os.environ, {"SERPAPI_API_KEY": "test"}, clear=True):
            connector = SerpApiConnector()
            with patch.object(connector, "_search", return_value={}) as search:
                connector.trends("robot educativo", "ES")
        self.assertEqual(search.call_args.args[0]["engine"], "google_trends")


if __name__ == "__main__":
    unittest.main()
