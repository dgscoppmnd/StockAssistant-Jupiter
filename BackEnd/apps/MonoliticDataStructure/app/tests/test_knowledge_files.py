import io
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import knowledge_files
from master_data_service import MasterDataError


class KnowledgeFileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.override = patch.object(knowledge_files, "KNOWLEDGE_DIR", self.root)
        self.override.start()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.override.stop)

    def upload(self, name, content):
        return SimpleNamespace(filename=name, file=io.BytesIO(content))

    def test_supported_formats_preserve_bytes_and_unique_names(self):
        for name, content in [("nota.TXT", b"hello"), ("nota.md", b"# Hello"), ("nota.pdf", b"%PDF-1.7\n")]:
            first = knowledge_files.store_file(self.upload(name, content))
            second = knowledge_files.store_file(self.upload(name, content))
            self.assertNotEqual(first, second)
            self.assertEqual(first.read_bytes(), content)
            self.assertEqual(first.parent, self.root)

    def test_rejects_invalid_files_without_leaving_partial_files(self):
        for name, content in [("bad.exe", b"hello"), ("empty.txt", b""), ("fake.pdf", b"hello"), ("binary.md", b"\xff\x00")]:
            with self.subTest(name=name), self.assertRaises(MasterDataError):
                knowledge_files.store_file(self.upload(name, content))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_size_limit_cleans_partial_file(self):
        with patch.object(knowledge_files, "MAX_FILE_SIZE", 3), self.assertRaises(MasterDataError) as error:
            knowledge_files.store_file(self.upload("large.txt", b"1234"))
        self.assertEqual(error.exception.status_code, 413)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_path_traversal_cannot_escape_storage(self):
        path = knowledge_files.store_file(self.upload("../../outside.txt", b"hello"))
        self.assertEqual(path.parent, self.root)

    def test_database_failure_removes_new_file(self):
        service = Mock()
        service.create.side_effect = MasterDataError("DB failure")
        with self.assertRaises(MasterDataError):
            knowledge_files.save_document(service, {"title": "test"}, self.upload("test.md", b"# test"))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_update_without_upload_preserves_reference(self):
        service = Mock()
        knowledge_files.save_document(service, {"title": "updated", "archivo": "../../evil"}, record_id=1)
        service.update.assert_called_once_with("knowledge-documents", 1, {"title": "updated"})

    def test_file_reference_is_saved_with_metadata(self):
        service = Mock()
        knowledge_files.save_document(service, {"title": "test"}, self.upload("test.txt", b"hello"))
        resource, values = service.create.call_args.args
        self.assertEqual(resource, "knowledge-documents")
        self.assertEqual((self.root / values["archivo"]).read_bytes(), b"hello")


if __name__ == "__main__":
    unittest.main()
