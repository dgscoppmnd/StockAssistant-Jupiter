import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from master_data_service import MasterDataError, MasterDataService, RESOURCES


class MasterDataRulesTests(unittest.TestCase):
    def setUp(self):
        self.service = MasterDataService(connection=None)

    def test_only_declared_master_resources_are_exposed(self):
        self.assertIn("units", RESOURCES)
        with self.assertRaises(MasterDataError):
            self.service._definition("inventory-movements")

    def test_unit_requires_code_and_name(self):
        definition = self.service._definition("units")
        with self.assertRaises(MasterDataError):
            self.service._values(definition, {"code": ""}, creating=True)

    def test_conversion_requires_positive_factor(self):
        definition = self.service._definition("unit-conversions")
        with self.assertRaises(MasterDataError):
            self.service._values(definition, {"from_unit_id": 1, "to_unit_id": 2, "factor": "0"}, creating=True)


if __name__ == "__main__":
    unittest.main()
