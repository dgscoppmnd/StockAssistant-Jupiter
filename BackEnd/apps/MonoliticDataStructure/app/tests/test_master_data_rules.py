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

    def test_client_code_preserves_leading_zeros_and_trims_spaces(self):
        values = self.service._values(RESOURCES["clients"], {
            "client_code": " 001-ABC ", "name": "Cliente", "fk_type_client": 1,
        }, creating=True)
        self.assertEqual(values["client_code"], "001-ABC")

    def test_client_can_still_be_created_without_code(self):
        values = self.service._values(RESOURCES["clients"], {
            "name": "Cliente", "fk_type_client": 1,
        }, creating=True)
        self.assertNotIn("client_code", values)

    def test_client_code_can_be_cleared(self):
        for code in ("", "   ", None):
            with self.subTest(code=code):
                values = self.service._values(RESOURCES["clients"], {
                    "client_code": code,
                }, creating=False)
                self.assertIsNone(values["client_code"])

    def test_partial_client_update_keeps_code_untouched(self):
        values = self.service._values(RESOURCES["clients"], {
            "fk_type_client": 2,
        }, creating=False)
        self.assertNotIn("client_code", values)

    def test_address_country_code_is_trimmed_and_uppercased(self):
        values = self.service._values(RESOURCES["global-addresses"], {
            "address_line_1": "Calle Mayor 1", "city": "Madrid", "country_code": " es ",
        }, creating=True)
        self.assertEqual(values["country_code"], "ES")

    def test_invalid_country_code_is_rejected_on_create_and_update(self):
        for creating in (True, False):
            for code in ("España", "ESP", "E", "12", "ÉS", "", None, 12):
                with self.subTest(creating=creating, code=code):
                    with self.assertRaises(MasterDataError) as error:
                        self.service._values(RESOURCES["global-addresses"], {
                            "address_line_1": "Calle Mayor 1", "city": "Madrid", "country_code": code,
                        }, creating=creating)
                    self.assertEqual(error.exception.status_code, 400)
                    self.assertIn("dos letras", str(error.exception))

    def test_partial_address_update_does_not_require_country_code(self):
        values = self.service._values(RESOURCES["global-addresses"], {"city": "Madrid"}, creating=False)
        self.assertEqual(values, {"city": "Madrid"})


if __name__ == "__main__":
    unittest.main()
