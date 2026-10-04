import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from knowledge_errors import KnowledgeError
from knowledge_pdf import extract_pdf_pages, merge_page_text


class NativePage:
    def __init__(self, text):
        self.text = text

    def extract_text(self):
        return self.text


class RenderedPage:
    def close(self):
        pass


class RenderedDocument:
    def __init__(self, _path):
        self.pages = [RenderedPage(), RenderedPage()]

    def __len__(self):
        return len(self.pages)

    def __getitem__(self, index):
        return self.pages[index]

    def close(self):
        pass


class KnowledgePdfTests(unittest.TestCase):
    def test_merge_preserves_native_and_adds_only_new_ocr_lines(self):
        merged = merge_page_text(
            "Política de devoluciones\nPlazo: 30 días",
            "Política de devoluciones\nPlazo: 30 días\nTeléfono en imagen: 900 123 123",
        )

        self.assertEqual(merged.count("Política de devoluciones"), 1)
        self.assertIn("Teléfono en imagen: 900 123 123", merged)

    def test_extract_combines_scanned_and_mixed_pages_and_reports_progress(self):
        pypdf = ModuleType("pypdf")
        pypdf.PdfReader = lambda _path: type(
            "Reader",
            (),
            {"is_encrypted": False, "pages": [NativePage(""), NativePage("Texto nativo")]},
        )()
        pdfium = ModuleType("pypdfium2")
        pdfium.PdfDocument = RenderedDocument
        progress = []

        with patch.dict(sys.modules, {"pypdf": pypdf, "pypdfium2": pdfium}), patch(
            "knowledge_pdf._ocr_page",
            side_effect=["Página escaneada", "Texto nativo\nDato en imagen"],
        ):
            pages = extract_pdf_pages(
                Path("manual.pdf"), lambda current, total: progress.append((current, total))
            )

        self.assertEqual(pages, [(1, "Página escaneada"), (2, "Texto nativo\nDato en imagen")])
        self.assertEqual(progress, [(1, 2), (2, 2)])

    def test_extract_reports_ocr_failure_with_page_number(self):
        pypdf = ModuleType("pypdf")
        pypdf.PdfReader = lambda _path: type(
            "Reader", (), {"is_encrypted": False, "pages": [NativePage("")]}
        )()
        pdfium = ModuleType("pypdfium2")
        pdfium.PdfDocument = lambda _path: type(
            "Document",
            (),
            {
                "__len__": lambda self: 1,
                "__getitem__": lambda self, _index: RenderedPage(),
                "close": lambda self: None,
            },
        )()

        with patch.dict(sys.modules, {"pypdf": pypdf, "pypdfium2": pdfium}), patch(
            "knowledge_pdf._ocr_page", side_effect=RuntimeError("timeout")
        ):
            with self.assertRaisesRegex(KnowledgeError, "página 1"):
                extract_pdf_pages(Path("scan.pdf"))


if __name__ == "__main__":
    unittest.main()
