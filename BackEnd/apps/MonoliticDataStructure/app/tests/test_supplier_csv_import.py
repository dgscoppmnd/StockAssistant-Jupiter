import csv
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from DataBaseManagement.supplier_csv_import import (
    ALTERNATE_CSV_COLUMNS,
    CSV_COLUMNS,
    import_supplier_csv,
    import_supplier_csv_events,
    parse_supplier_csv,
)


def make_csv(header=CSV_COLUMNS, **overrides):
    row = {"supplier_code": "PRV-001", "name": "Proveedor Uno", "email": "ventas@example.com", "phone": "+34 600 000 000",
           "code_proveedor": "PRV-001", "name_supplier": "Proveedor Uno"}
    row.update(overrides)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(header)
    writer.writerow([row[field] for field in header])
    return output.getvalue().encode("utf-8-sig")


class SupplierCsvImportTests(unittest.TestCase):
    def test_parses_primary_and_alternate_headers(self):
        for header in (CSV_COLUMNS, ALTERNATE_CSV_COLUMNS):
            with self.subTest(header=header):
                supplier = parse_supplier_csv(make_csv(header))[0]
                self.assertEqual(supplier.code, "PRV-001")
                self.assertEqual(supplier.name, "Proveedor Uno")

    def test_rejects_required_fields_and_duplicates(self):
        for content in (b"", b"wrong,header\n", make_csv(supplier_code=""), make_csv(name="")):
            with self.subTest(content=content[:30]), self.assertRaises(ValueError):
                parse_supplier_csv(content)
        decoded = make_csv().decode("utf-8-sig")
        with self.assertRaisesRegex(ValueError, "repetido"):
            parse_supplier_csv((decoded + decoded.split("\r\n", 1)[1]).encode())

    def test_imports_or_skips_existing_code(self):
        for existing, imported in (([], 1), ([('PRV-001', 'Proveedor Uno')], 0)):
            db = MagicMock()
            cursor = db.cursor.return_value.__enter__.return_value
            cursor.fetchall.return_value = existing
            result = import_supplier_csv(make_csv(), db)
            self.assertEqual(result, {"imported": imported, "skipped": 1 - imported, "total": 1})
            inserts = [call for call in cursor.execute.call_args_list if "INSERT INTO" in call.args[0]]
            self.assertEqual(len(inserts), imported)

    def test_existing_name_with_another_code_rolls_back(self):
        db = MagicMock()
        cursor = db.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [("OTHER", "Proveedor Uno")]
        seen = []
        with self.assertRaisesRegex(ValueError, "otro código"):
            for event in import_supplier_csv_events(make_csv(), db):
                seen.append(event)
        self.assertFalse(any(event["stage"] == "complete" for event in seen))
        self.assertIs(db.__exit__.call_args.args[0], ValueError)


if __name__ == "__main__":
    unittest.main()
