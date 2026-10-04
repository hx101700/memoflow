"""验证临时文件归属及配置发布失败后的清理边界。"""

import json
import os
from pathlib import Path
from unittest.mock import patch

from asr_runtime import MODEL
from asr_runtime.utils.documents import publish_document, write_markdown
from asr_runtime.utils.environment import SetupError
from asr_runtime.utils.files import write_json_atomic
from asr_runtime.utils.job_files import document_directory, job_directory, publish_config
from tests.support import RuntimeTestCase
from tests.test_documents import sample


class TemporaryWriterTests(RuntimeTestCase):
    def setUp(self):
        """准备仅供本机文件发布测试使用的最小配置。"""
        super().setUp()
        self.job_id = "a" * 32
        self.config = {
            "job_id": self.job_id,
            "document_directory": str(self.runtime.output_root / self.job_id / "documents"),
        }

    def test_json_and_document_temporary_names_identify_the_writer_process(self):
        """验证两种原子写入都标注进程且只留下最终文件。"""
        paths = []
        replace = Path.replace

        def observe_replace(source, destination):
            """记录实际发布文件名后完成原子替换。"""
            paths.append(source)
            return replace(source, destination)

        record = self.runtime.path("status.json")
        document = self.runtime.path("transcription.md")
        with patch.object(Path, "replace", autospec=True, side_effect=observe_replace):
            write_json_atomic(record, {"status": "synthetic"})
            publish_document(write_markdown, sample(), document,
                             source_name="synthetic.wav", job_id=self.job_id, model=MODEL)
        self.assertRegex(paths[0].name, rf"^status\.json\.pid-{os.getpid()}-[\w-]+\.tmp$")
        self.assertRegex(paths[1].name, rf"^transcription\.partial-pid-{os.getpid()}-[\w-]+\.md$")
        self.assertEqual(json.loads(record.read_text(encoding="utf-8")), {"status": "synthetic"})
        self.assertTrue(document.is_file())
        self.assertTrue(all(not path.exists() for path in paths))

    def test_failed_configuration_writes_remove_unpublished_files(self):
        """验证配置、摘要或最终发布失败均回收本次未提交目录。"""
        for stage in ("config", "checksum", "publication"):
            with self.subTest(stage=stage):
                failure = OSError("synthetic disk failure")
                if stage == "publication":
                    failure_point = patch.object(Path, "replace", side_effect=failure)
                else:
                    failures = [failure] if stage == "config" else [None, failure]
                    failure_point = patch("asr_runtime.utils.job_files.os.fsync", side_effect=failures)
                with failure_point, self.assertRaises(OSError):
                    publish_config(self.runtime, self.config)
                self.assertFalse(job_directory(self.runtime, self.job_id).exists())

    def test_interrupt_during_configuration_write_removes_unpublished_files(self):
        """验证可捕获中断也会回收未发布配置。"""
        with patch("asr_runtime.utils.job_files.os.fsync", side_effect=KeyboardInterrupt), \
                self.assertRaises(KeyboardInterrupt):
            publish_config(self.runtime, self.config)
        self.assertFalse(job_directory(self.runtime, self.job_id).exists())

    def test_existing_job_directory_is_preserved_when_publication_is_refused(self):
        """验证独占创建失败时保留已有任务的所有文件。"""
        directory = job_directory(self.runtime, self.job_id)
        directory.mkdir(parents=True)
        sentinel = directory / "config.json"
        sentinel.write_bytes(b"synthetic existing config")
        with self.assertRaises(FileExistsError):
            publish_config(self.runtime, self.config)
        self.assertEqual(sentinel.read_bytes(), b"synthetic existing config")

    def test_interrupt_after_publication_preserves_the_committed_configuration(self):
        """验证配置已发布后的中断保留交接提交标记及摘要。"""
        replace = Path.replace

        def interrupt_after_replace(source, destination):
            """完成原子发布后模拟进程收到可捕获中断。"""
            replace(source, destination)
            raise KeyboardInterrupt

        with patch.object(Path, "replace", autospec=True, side_effect=interrupt_after_replace), \
                self.assertRaises(KeyboardInterrupt):
            publish_config(self.runtime, self.config)
        directory = job_directory(self.runtime, self.job_id)
        self.assertEqual(json.loads((directory / "config.json").read_text(encoding="utf-8")), self.config)
        self.assertTrue((directory / "config.sha256").is_file())

    def test_document_location_check_has_no_directory_creation(self):
        """验证共享路径检查只返回正确的任务目录。"""
        destination = document_directory(self.config)
        self.assertEqual(destination, Path(self.config["document_directory"]))
        self.assertFalse(destination.exists())
        self.config["document_directory"] = str(self.runtime.output_root / ("b" * 32) / "documents")
        with self.assertRaises(SetupError):
            document_directory(self.config)
