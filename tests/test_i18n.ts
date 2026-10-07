import assert from "node:assert/strict";
import test from "node:test";
import { durationText, fileSize, languageName, localize, translate } from "../frontend/i18n";
import { UiError, uiError } from "../frontend/api";
import type { Language } from "../frontend/types";
import { isDark, readPreferences } from "../frontend/preferences";

test("深浅色显式选择和系统配色遵循同一规则", () => {
  assert.equal(isDark("system", true), true);
  assert.equal(isDark("system", false), false);
  assert.equal(isDark("light", true), false);
  assert.equal(isDark("dark", false), true);
});

test("偏好仅包含语言和主题；存储不可用时仍可打开", () => {
  const saved = { getItem: () => JSON.stringify({ language: "en", theme: "dark", apiKey: "fixture" }) };
  assert.deepEqual(readPreferences(saved, "zh-CN"), { language: "en", theme: "dark" });
  assert.deepEqual(readPreferences({ getItem() { throw new Error("Storage blocked"); } }, "en-US"), { language: "en", theme: "system" });
  assert.deepEqual(readPreferences({ getItem: () => "null" }, "zh-CN"), { language: "zh-CN", theme: "system" });
});

test("英文使用Model Studio与speaker diarization术语", () => {
  assert.equal(translate("en", "provider"), "Speech recognition by Alibaba Cloud Model Studio");
  assert.equal(translate("en", "diarization"), "Speaker diarization");
  assert.equal(languageName("tl", "en"), "Filipino");
  assert.equal(languageName("de", "en"), "German");
  assert.equal(translate("en", "contextHint", { count: 400 }).includes("400"), true);
});

test("文案替换保留用户文件名、花括号和Unicode原文", () => {
  const name = "<script>{count} & 😀.wav";
  assert.equal(translate("en", "importedHotwords", { name }), `Imported: ${name}`);
});

test("文件大小与服务端十进制限制一致，时长跨语言一致", () => {
  assert.equal(fileSize(5_000_000), "5.00 MB");
  assert.equal(durationText(3671), "01:01:11");
});

test("服务端错误和警告按当前语言读取，原始位置及双语内容保持不变", () => {
  const text = { zh: "请修改权重。", en: "Correct the weight." };
  const issue = { row: 2, field: "weight", message: text };
  const error = new UiError(text, "hotword_rows", 422, [issue]);
  assert.equal(error.describe("zh-CN"), "请修改权重。");
  assert.equal(error.describe("en"), "Correct the weight.");
  assert.equal(localize(text, "en"), "Correct the weight.");
  assert.equal(error.details[0], issue);
  assert.equal(error.details[0].row, 2);
  assert.deepEqual(text, { zh: "请修改权重。", en: "Correct the weight." });
});

test("本机提示随语言切换更新，未知异常内容不泄露给页面", () => {
  let language: Language = "zh-CN";
  const local = new UiError(() => translate(language, "missingAudio"), "audio_id");
  const unknown = uiError(new Error("private technical detail"), () => translate(language, "failed"));
  assert.equal(local.describe(language), "请选择录音。");
  language = "en";
  assert.equal(local.describe(language), "Choose a recording.");
  assert.equal(unknown.describe(language), translate("en", "failed"));
  assert.equal(unknown.describe(language).includes("private technical detail"), false);
});
