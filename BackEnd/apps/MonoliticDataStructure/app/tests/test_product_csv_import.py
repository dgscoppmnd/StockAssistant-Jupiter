import csv
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from DataBaseManagement.product_csv_import import (
    CSV_COLUMNS, MAX_CSV_BYTES, IMPORT_BATCH_SIZE, import_product_csv, parse_product_csv, iter_product_csv,
    import_product_csv_events,
)


def make_csv(**overrides):
    row = dict(zip(CSV_COLUMNS, ["PRD1", "Café", 'Descripción, con "comillas"\ny salto',
                               "Home", "Marca", "SKU1", "12.30", "25.50", "2026-05-25 10:08:16"]))
    row.update(overrides)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(CSV_COLUMNS)
    writer.writerow([row[field] for field in CSV_COLUMNS])
    return output.getvalue().encode("utf-8-sig")


class ProductCsvImportTests(unittest.TestCase):
    def test_progress_confirms_completion_only_after_commit(self):
        db = MagicMock()
        cursor = db.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (2,)
        cursor.fetchall.return_value = [("PRD1",)]
        events = import_product_csv_events(make_csv(), db)
        seen = []
        for event in events:
            seen.append(event)
            if event["stage"] == "committing":
                db.__exit__.assert_not_called()
            if event["stage"] == "complete":
                db.__exit__.assert_called_once_with(None, None, None)
        self.assertEqual(seen[-1]["result"], {"imported": 0, "skipped": 1, "total": 1})
        self.assertEqual([event["percent"] for event in seen if event["stage"] == "importing"], [0, 100])

    def test_commit_failure_never_reports_completion(self):
        db = MagicMock()
        cursor = db.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (2,)
        cursor.fetchall.return_value = []
        db.__exit__.side_effect = RuntimeError("commit failed")
        seen = []
        with self.assertRaises(RuntimeError):
            for event in import_product_csv_events(make_csv(), db):
                seen.append(event)
        self.assertEqual(seen[-1]["stage"], "committing")
        self.assertFalse(any(event["stage"] == "complete" for event in seen))

    def test_exact_200_mb_and_one_byte_over(self):
        self.assertEqual(MAX_CSV_BYTES, 200 * 1024 * 1024)
        with tempfile.TemporaryFile() as source:
            source.write(make_csv())
            # Filas vacías válidas: tamaño real de 200 MB sin acumularlo en RAM.
            padding = b" " * 65535 + b"\n"
            remaining = MAX_CSV_BYTES - source.tell()
            while remaining:
                chunk = padding if remaining >= len(padding) else b" " * (remaining - 1) + b"\n"
                source.write(chunk)
                remaining -= len(chunk)
            self.assertEqual(sum(1 for _ in iter_product_csv(source)), 1)
            self.assertFalse(source.closed)
            source.seek(0, io.SEEK_END)
            source.write(b"\n")
            with self.assertRaisesRegex(ValueError, "200 MB"):
                list(iter_product_csv(source))

    def test_large_import_uses_bounded_batches(self):
        with tempfile.TemporaryFile() as source:
            source.write((",".join(CSV_COLUMNS) + "\n").encode())
            for number in range(10001):
                source.write(f"PRD{number},Producto,{'x' * 600},Home,Marca,SKU,1,2,2026-05-25 10:08:16\n".encode())
            self.assertGreater(source.tell(), 5 * 1024 * 1024)
            db = MagicMock()
            cursor = db.cursor.return_value.__enter__.return_value
            cursor.fetchone.return_value = (2,)
            cursor.fetchall.return_value = []
            result = import_product_csv(source, db)
            self.assertEqual(result, {"imported": 10001, "skipped": 0, "total": 10001})
            inserts = [call for call in cursor.execute.call_args_list if "INSERT INTO" in call.args[0]]
            self.assertEqual(len(inserts), 11)
            self.assertTrue(all(len(call.args[1]) <= IMPORT_BATCH_SIZE * 8 for call in inserts))
            self.assertFalse(source.closed)

    def test_example_file(self):
        root = Path(__file__).resolve().parents[5]
        products = parse_product_csv((root / "datacsv/formatoEjemploProductos.csv").read_bytes())
        self.assertEqual(len(products), 3)
        self.assertEqual(products[0].cdgo_producto_externo, "PRD0000001")
        self.assertEqual(products[0].price, 703.03)
        self.assertEqual(products[0].final_price, 3631.04)

    def test_quotes_bom_multiline_and_mapping(self):
        product = parse_product_csv(make_csv())[0]
        self.assertEqual(product.name_product, "Café")
        self.assertIn('Descripción, con "comillas"\ny salto', product.description_product)
        self.assertIn("Categoría: Home\nMarca: Marca\nSKU: SKU1", product.description_product)
        self.assertEqual(product.currency, "USD")
        self.assertIsNotNone(product.creation_date.tzinfo)

    def test_invalid_fields(self):
        for values in [{"product_id": ""}, {"product_name": ""}, {"created_at": "2026-02-30 00:00:00"},
                       {"product_cost_usd": "NaN"}, {"selling_price_usd": "Infinity"},
                       {"product_cost_usd": "-1"}, {"selling_price_usd": "abc"},
                       {"description": "x" * 1001}]:
            with self.subTest(values=values), self.assertRaisesRegex(ValueError, "Línea"):
                parse_product_csv(make_csv(**values))

    def test_invalid_csv(self):
        for content in [b"", b"wrong,header\n", (",".join(CSV_COLUMNS) + "\n").encode(),
                        make_csv() + b'"unterminated', b"\xff", make_csv() + b"too,few\n"]:
            with self.subTest(content=content[:20]), self.assertRaises(ValueError):
                parse_product_csv(content)

    def test_duplicate_ids(self):
        content = make_csv().decode("utf-8-sig")
        with self.assertRaisesRegex(ValueError, "repetido"):
            parse_product_csv((content + content.split("\r\n", 1)[1]).encode())

    def test_skip_existing_and_currency(self):
        for existing, count in [([], 1), ([("PRD1",)], 0)]:
            db = MagicMock()
            cursor = db.cursor.return_value.__enter__.return_value
            cursor.fetchall.return_value = existing
            cursor.fetchone.return_value = (2,)
            result = import_product_csv(make_csv(), db)
            self.assertEqual(result, {"imported": count, "skipped": 1 - count, "total": 1})
            inserts = [call for call in cursor.execute.call_args_list if "INSERT INTO" in call.args[0]]
            self.assertEqual(len(inserts), count)
            if count:
                self.assertEqual(inserts[0].args[1][-1], 2)
            db.__exit__.assert_called_once_with(None, None, None)

    def test_validation_before_database_access(self):
        db = MagicMock()
        with self.assertRaises(ValueError):
            import_product_csv(make_csv(product_cost_usd="invalid"), db)
        db.cursor.assert_not_called()

    def test_database_failure_exits_transaction_with_error(self):
        db = MagicMock()
        cursor = db.cursor.return_value.__enter__.return_value
        cursor.execute.side_effect = RuntimeError("database failure")
        with self.assertRaises(RuntimeError):
            import_product_csv(make_csv(), db)
        self.assertIs(db.__exit__.call_args.args[0], RuntimeError)


if __name__ == "__main__":
    unittest.main()
