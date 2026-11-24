"""验证任务查询只读本工作区元信息，局部损坏不会隐藏其余候选。"""

import io
import json
from contextlib import redirect_stdout
from unittest.mock import patch

from asr_runtime import MODEL
from asr_runtime.__main__ import main
from asr_runtime.application.transcription import list_jobs
from asr_runtime.utils.job_files import job_directory, publish_config, save_record
from tests.support import RuntimeTestCase


class JobListingTests(RuntimeTestCase):
    def make_job(self, job_id, name, confirmed_at, status=None):
        """发布带合成私有内容的确认配置，并按需保存本机执行状态。"""
        base = self.runtime.workspace / "results" / job_id
        config = {
            "schema_version": 1, "job_id": job_id, "model": MODEL, "region": "cn-beijing",
            "auth_mode": "console", "audio": {"name": name, "path": str(self.runtime.workspace / name)},
            "diarization_enabled": True, "recognition_options": {"language_hints": [], "speaker_count": None},
            "enhancement": {"mode": "context", "hotwords": None, "context": "private-context-sentinel"},
            "json_directory": str(base / "json"), "document_directory": str(base / "documents"),
            "status": "CONFIGURED", "execution_authorized": True, "confirmed_at": confirmed_at,
        }
        publish_config(self.runtime, config)
        directory = job_directory(self.runtime, job_id)
        if status is not None:
            (directory / "execution").mkdir()
            save_record(directory / "execution", {"job_id": job_id, "status": status,
                        "message": "private-status-sentinel"})
        return directory

    def test_empty_workspace_returns_empty_without_creating_state(self):
        """尚无任务时返回空列表，查询不创建任务目录或运行环境。"""
        self.assertEqual(list_jobs(self.runtime), {"jobs": [], "issues": []})
        self.assertFalse(self.runtime.path(".state").exists())

    def test_query_matches_recording_or_id_and_keeps_multiple_candidates(self):
        """名称和编号支持大小写无关的包含匹配，多个候选按确认时间倒序返回。"""
        self.make_job("a" * 32, "周会 Meeting.wav", "2026-11-22T08:00:00+00:00")
        self.make_job("b" * 32, "周会 MEETING.wav", "2026-11-23T08:00:00+00:00", "JSON_READY")
        self.make_job("c" * 32, "访谈.wav", "2026-11-24T08:00:00+00:00", "STOPPED")
        result = list_jobs(self.runtime, " meeting ")
        self.assertEqual(result, {"jobs": [
            {"job_id": "b" * 32, "audio_name": "周会 MEETING.wav",
             "confirmed_at": "2026-11-23T08:00:00+00:00", "status": "JSON_READY"},
            {"job_id": "a" * 32, "audio_name": "周会 Meeting.wav",
             "confirmed_at": "2026-11-22T08:00:00+00:00", "status": "CONFIGURED"},
        ], "issues": []})
        self.assertEqual([job["job_id"] for job in list_jobs(self.runtime, "BBB")["jobs"]], ["b" * 32])
        self.assertEqual(list_jobs(self.runtime, "不存在的录音"), {"jobs": [], "issues": []})
        self.assertEqual([job["job_id"] for job in list_jobs(self.runtime)["jobs"]], ["c" * 32, "b" * 32, "a" * 32])

    def test_invalid_confirmation_reports_issue_beside_valid_jobs(self):
        """摘要不符或未发布完成的配置分别报告实际问题，其余有效任务仍返回。"""
        self.make_job("a" * 32, "可用录音.wav", "2026-11-24T08:00:00+00:00")
        changed = self.make_job("b" * 32, "已改变.wav", "2026-11-23T08:00:00+00:00")
        (changed / "config.json").write_text("{}", encoding="utf-8")
        self.runtime.path(f".state/jobs/{'c' * 32}").mkdir()
        result = list_jobs(self.runtime)
        self.assertEqual([job["job_id"] for job in result["jobs"]], ["a" * 32])
        self.assertEqual([issue["job_id"] for issue in result["issues"]], ["b" * 32, "c" * 32])
        self.assertIn("配置发生变化", result["issues"][0]["message"])
        self.assertIn("缺少确认摘要", result["issues"][1]["message"])

    def test_execution_damage_keeps_candidate_with_unknown_status(self):
        """已占用任务的执行记录不可读时保留候选，明确标记未知并报告原因。"""
        damaged = self.make_job("a" * 32, "待核对录音.wav", "2026-11-24T08:00:00+00:00", "RUNNING")
        (damaged / "execution/status.json").write_text("invalid-json", encoding="utf-8")
        self.make_job("b" * 32, "完成录音.wav", "2026-11-23T08:00:00+00:00", "JSON_READY")
        result = list_jobs(self.runtime)
        self.assertEqual([job["status"] for job in result["jobs"]], ["OUTCOME_UNKNOWN", "JSON_READY"])
        self.assertEqual(result["issues"][0]["job_id"], "a" * 32)
        self.assertIn("执行记录不可读", result["issues"][0]["message"])

    def test_query_does_not_read_review_or_secrets_and_preserves_files(self):
        """查询不打开正文或校对记录、不读Key、不调用BL，磁盘文件保持不变。"""
        directory = self.make_job("a" * 32, "元信息.wav", "2026-11-24T08:00:00+00:00", "JSON_READY")
        (directory / "review").mkdir()
        (directory / "review/draft.json").write_text("private-review-sentinel", encoding="utf-8")
        self.runtime.path(".env").write_text("DASHSCOPE_API_KEY=private-key-sentinel", encoding="utf-8")
        before = {file: file.read_bytes() for file in self.runtime.root.rglob("*") if file.is_file()}
        with patch("asr_runtime.application.review.read_review_status", side_effect=AssertionError("must not read review")), \
             patch("asr_runtime.utils.auth.read_api_key", side_effect=AssertionError("must not read API Key")), \
             patch("asr_runtime.application.transcription.load_transcript", side_effect=AssertionError("must not read transcript")), \
             patch("asr_runtime.application.transcription.run_recognition", side_effect=AssertionError("must not call BL")):
            result = list_jobs(self.runtime)
        self.assertEqual(result["issues"], [])
        self.assertEqual(set(result["jobs"][0]), {"job_id", "audio_name", "confirmed_at", "status"})
        self.assertNotIn("private-", json.dumps(result))
        self.assertEqual(before, {file: file.read_bytes() for file in self.runtime.root.rglob("*") if file.is_file()})

    def test_cli_reports_candidates_even_with_local_issues(self):
        """CLI输出可解析候选和局部问题，遵循现有问题退出码而不丢弃结果。"""
        self.make_job("a" * 32, "会议.wav", "2026-11-24T08:00:00+00:00")
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["--workspace", str(self.runtime.workspace), "jobs", "--query", "会议"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["jobs"][0]["job_id"], "a" * 32)
        self.runtime.path(f".state/jobs/{'b' * 32}").mkdir()
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["--workspace", str(self.runtime.workspace), "jobs"])
        self.assertEqual(code, 1)
        result = json.loads(output.getvalue())
        self.assertEqual(result["jobs"][0]["job_id"], "a" * 32)
        self.assertEqual(result["issues"][0]["job_id"], "b" * 32)
