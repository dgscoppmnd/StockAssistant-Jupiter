import json
import os
import unittest
from unittest.mock import MagicMock, patch

import file_storage
import knowledge_files
import knowledge_worker
from master_data_service import MasterDataService


class KnowledgeTriggerTests(unittest.TestCase):
    def test_lambda_dispatches_without_waking_local_worker(self):
        with patch.object(file_storage, "IS_LAMBDA", True), patch.object(
            file_storage, "trigger_indexing"
        ) as trigger, patch.object(knowledge_worker, "_wake") as wake:
            knowledge_worker.notify_knowledge_worker()
        trigger.assert_called_once_with()
        wake.set.assert_not_called()

    def test_local_wakes_worker_without_invoking_lambda(self):
        with patch.object(file_storage, "IS_LAMBDA", False), patch.object(
            file_storage, "trigger_indexing"
        ) as trigger, patch.object(knowledge_worker, "_wake") as wake:
            knowledge_worker.notify_knowledge_worker()
        trigger.assert_not_called()
        wake.set.assert_called_once_with()

    def test_lambda_payload_is_async_and_authenticated(self):
        with patch.object(file_storage, "IS_LAMBDA", True), patch.dict(
            os.environ,
            {
                "AWS_LAMBDA_FUNCTION_NAME": "test-function",
                "STOCKASSISTANT_SESSION_SECRET": "test-only-secret",
            },
        ), patch("boto3.client") as client:
            knowledge_worker.notify_knowledge_worker()
        client.assert_called_once_with("lambda")
        kwargs = client.return_value.invoke.call_args.kwargs
        self.assertEqual(kwargs["FunctionName"], "test-function")
        self.assertEqual(kwargs["InvocationType"], "Event")
        self.assertEqual(json.loads(kwargs["Payload"]), {"jupiter_index": "test-only-secret"})

    def test_create_update_reindex_delete_dispatch_after_commit(self):
        for operation in ("create", "update", "reindex", "delete"):
            with self.subTest(operation=operation):
                connection = MagicMock()
                cursor = connection.cursor.return_value.__enter__.return_value
                cursor.fetchone.return_value = {"id": 2}
                cursor.rowcount = 1
                service = MasterDataService(connection)
                with patch.object(service, "get", return_value={"id": 2}), patch.object(
                    file_storage, "IS_LAMBDA", True
                ), patch.object(file_storage, "trigger_indexing") as trigger:
                    trigger.side_effect = lambda: connection.commit.assert_called_once_with()
                    if operation == "create":
                        service.create("knowledge-documents", {
                            "title": "test", "content": "test content", "source": "test"
                        })
                    elif operation == "update":
                        service.update("knowledge-documents", 2, {"title": "updated"})
                    elif operation == "reindex":
                        service.reindex_knowledge_document(2)
                    else:
                        service.delete("knowledge-documents", 2)
                trigger.assert_called_once_with()

    def test_failed_commit_does_not_dispatch(self):
        connection = MagicMock()
        connection.commit.side_effect = RuntimeError("commit failed")
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {"id": 2}
        with patch.object(file_storage, "trigger_indexing") as trigger:
            with self.assertRaisesRegex(RuntimeError, "commit failed"):
                MasterDataService(connection).create("knowledge-documents", {
                    "title": "test", "content": "content", "source": "test"
                })
        trigger.assert_not_called()

    def test_upload_dispatches_once_through_service(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {"id": 2}
        service = MasterDataService(connection)
        path = MagicMock()
        path.name = "test.txt"
        with patch.object(service, "get", return_value={"id": 2}), patch.object(
            knowledge_files, "store_file", return_value=path
        ), patch.object(file_storage, "IS_LAMBDA", True), patch.object(
            file_storage, "trigger_indexing"
        ) as trigger:
            knowledge_files.save_document(service, {
                "title": "test", "content": "content", "source": "test"
            }, upload=MagicMock())
        trigger.assert_called_once_with()

    def test_missing_secret_is_logged_without_invocation(self):
        with patch.object(file_storage, "IS_LAMBDA", True), patch.dict(
            os.environ, {"STOCKASSISTANT_SESSION_SECRET": ""}
        ), patch("boto3.client") as client, self.assertLogs(
            file_storage.LOGGER, level="WARNING"
        ) as logs:
            knowledge_worker.notify_knowledge_worker()
        client.assert_not_called()
        self.assertIn("index_trigger_skipped reason=no_secret", logs.output[0])

    def test_invoke_failure_is_logged_and_secret_not_printed(self):
        with patch.object(file_storage, "IS_LAMBDA", True), patch.dict(
            os.environ,
            {"AWS_LAMBDA_FUNCTION_NAME": "test", "STOCKASSISTANT_SESSION_SECRET": "test-secret"},
        ), patch("boto3.client") as client, self.assertLogs(
            file_storage.LOGGER, level="WARNING"
        ) as logs:
            client.return_value.invoke.side_effect = RuntimeError("invoke failed")
            knowledge_worker.notify_knowledge_worker()
        self.assertIn("index_trigger_failed", logs.output[0])
        self.assertNotIn("test-secret", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
