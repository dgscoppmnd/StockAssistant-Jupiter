import csv
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from DataBaseManagement.client_csv_import import (
    ALTERNATE_CSV_COLUMNS,
    CSV_COLUMNS,
    import_client_csv,
    import_client_csv_events,
    parse_client_csv,
)


def make_csv(header=CSV_COLUMNS, **overrides):
    row = {
        "code_cliente": "CLI-001",
        "name_client": "Cliente de prueba",
        "description": 'Descripcion, con "comillas"',
        "tipo_cliente": "Activo",
        "tipo cliente": "Activo",
    }
    row.update(overrides)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(header)
    writer.writerow([row[field] for field in header])
    return output.getvalue().encode("utf-8-sig")


class ClientCsvImportTests(unittest.TestCase):
    def test_parses_bom_quotes_and_alternate_header(self):
        for header in (CSV_COLUMNS, ALTERNATE_CSV_COLUMNS):
            with self.subTest(header=header):
                client = parse_client_csv(make_csv(header))[0]
                self.assertEqual(client.code, "CLI-001")
                self.assertEqual(client.name, "Cliente de prueba")
                self.assertEqual(client.client_type, "Activo")

    def test_rejects_invalid_rows_and_duplicate_codes(self):
        for content in (
            b"",
            b"wrong,header\n",
            make_csv(code_cliente=""),
            make_csv(name_client=""),
            make_csv(tipo_cliente=""),
        ):
            with self.subTest(content=content[:30]), self.assertRaises(ValueError):
                parse_client_csv(content)
        decoded = make_csv().decode("utf-8-sig")
        with self.assertRaisesRegex(ValueError, "repetido"):
            parse_client_csv((decoded + decoded.split("\r\n", 1)[1]).encode())

    def test_import_maps_type_and_skips_existing_code(self):
        for existing, imported in (([], 1), ([('CLI-001',)], 0)):
            db = MagicMock()
            cursor = db.cursor.return_value.__enter__.return_value
            cursor.fetchall.side_effect = [[(4, "Activo")], existing]
            result = import_client_csv(make_csv(), db)
            self.assertEqual(result, {"imported": imported, "skipped": 1 - imported, "total": 1})
            inserts = [call for call in cursor.execute.call_args_list if "INSERT INTO" in call.args[0]]
            self.assertEqual(len(inserts), imported)
            if inserts:
                self.assertEqual(inserts[0].args[1], ("CLI-001", "Cliente de prueba", 'Descripcion, con "comillas"', 4))

    def test_unknown_type_rolls_back_and_never_completes(self):
        db = MagicMock()
        cursor = db.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [(1, "Propio")]
        seen = []
        with self.assertRaisesRegex(ValueError, "Activo"):
            for event in import_client_csv_events(make_csv(), db):
                seen.append(event)
        self.assertFalse(any(event["stage"] == "complete" for event in seen))
        self.assertIs(db.__exit__.call_args.args[0], ValueError)


if __name__ == "__main__":
    unittest.main()
