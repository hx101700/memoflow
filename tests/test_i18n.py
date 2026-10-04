"""验证网页消息的语言作用域、并发隔离和模板参数。"""

from concurrent.futures import ThreadPoolExecutor
from string import Formatter
from threading import Barrier
import unittest

from asr_runtime.utils.i18n import _ENGLISH, language_scope, localize, translate
from asr_runtime.application.rules import ValidationError, build_vocabulary
from asr_runtime.models import HotwordRow


class LocalizationTests(unittest.TestCase):
    def test_nested_scope_restores_language_after_error(self) -> None:
        """验证嵌套请求结束或异常时恢复外层语言。"""
        message = "请选择音频文件。"
        self.assertEqual(translate(message), message)
        with language_scope("en-US,en;q=0.9"):
            self.assertEqual(translate(message), "Choose an audio file.")
            with self.assertRaises(ValueError):
                with language_scope("zh-CN"):
                    self.assertEqual(translate(message), message)
                    raise ValueError("synthetic request error")
            self.assertEqual(translate(message), "Choose an audio file.")
        self.assertEqual(translate(message), message)

    def test_concurrent_requests_keep_their_own_language(self) -> None:
        """验证并发请求的中英文提示互不影响。"""
        barrier = Barrier(2)

        def render(language: str) -> str:
            """在同步到达的请求作用域中读取提示。"""
            with language_scope(language):
                barrier.wait(timeout=5)
                return translate("请选择音频文件。")

        with ThreadPoolExecutor(max_workers=2) as pool:
            english = pool.submit(render, "en")
            chinese = pool.submit(render, "zh-CN")
            self.assertEqual(english.result(timeout=5), "Choose an audio file.")
            self.assertEqual(chinese.result(timeout=5), "请选择音频文件。")

    def test_unknown_language_and_user_content_keep_original_text(self) -> None:
        """验证未支持的语言使用中文，未登记的用户文本保持原样。"""
        with language_scope("fr"):
            self.assertEqual(translate("请选择音频文件。"), "请选择音频文件。")
        private_text = "会议术语 C:\\录音\\recording.wav — {value}"
        with language_scope("en"):
            self.assertEqual(translate(private_text), private_text)

    def test_dynamic_message_keeps_all_named_parameters(self) -> None:
        """验证目录中的中英文模板保留相同参数并正确呈现动态值。"""
        formatter = Formatter()
        for source, english in _ENGLISH.items():
            with self.subTest(source=source):
                self.assertEqual(
                    {name for _, name, _, _ in formatter.parse(source) if name},
                    {name for _, name, _, _ in formatter.parse(english) if name},
                )
        with language_scope("en"):
            text = translate("已忽略{count}个完全空白行。", count=2)
        self.assertEqual(text, "Empty rows skipped: 2.")

    def test_localized_messages_keep_both_languages_and_raw_values(self) -> None:
        """验证双语结果与当前语言无关，模板参数中的花括号保持原文。"""
        template = "资源路径指向Skill目录外：{relative}"
        path = "录音/{original}.wav"
        expected = {"zh": f"资源路径指向Skill目录外：{path}",
                    "en": f"The resource path points outside the Skill installation: {path}"}
        for language in ("zh-CN", "en"):
            with language_scope(language):
                self.assertEqual(localize(template, relative=path), expected)
                self.assertEqual(localize(path), {"zh": path, "en": path})

    def test_hotword_notices_translate_locations_and_keep_user_terms(self) -> None:
        """验证重复错误同时携带双语与关联行号，用户词条保持原文。"""
        rows = [HotwordRow(text="产品术语", weight=4), HotwordRow(text="产品术语", weight=4),
                HotwordRow(text=None, weight=None)]
        with language_scope("en"), self.assertRaises(ValidationError) as caught:
            build_vocabulary(rows)
        self.assertEqual([issue["row"] for issue in caught.exception.details], [1, 2])
        self.assertTrue(all(issue["duplicate_group"] == 1 for issue in caught.exception.details))
        self.assertTrue(all(issue["message"] == {
            "zh": "存在重复数据，请保留至一行", "en": "Duplicate entries. Keep only one row.",
        } for issue in caught.exception.details))
        with language_scope("en"):
            result = build_vocabulary([rows[0], rows[2]])
        self.assertEqual(result["vocabulary"], {"产品术语": 4})
        self.assertEqual(result["warnings"], [
            {"zh": "已忽略1个完全空白行。", "en": "Empty rows skipped: 1."},
        ])
        with language_scope("en"), self.assertRaises(ValidationError) as caught:
            build_vocabulary([rows[0], HotwordRow(text="产品术语", weight=5)])
        self.assertEqual([issue["row"] for issue in caught.exception.details], [1, 2])
        self.assertEqual([issue["field"] for issue in caught.exception.details], ["text", "text"])
