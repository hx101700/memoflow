import assert from "node:assert/strict";
import test from "node:test";
import { useTranscription, type ViewEffects } from "../frontend/useTranscription";
import { useReview } from "../frontend/useReview";
import { ReviewRequestError, sentenceModified, createReviewApi } from "../frontend/review";
import type { ReviewApi, ReviewDocument, ReviewEndpoints } from "../frontend/types";
import { createApi, UiError } from "../frontend/api";
import { availability, configuration, createModel, hotwordRows } from "../frontend/model";
import { localize, translate, type Translate } from "../frontend/i18n";
import type { Api, Configuration, EditorIssue, Endpoints, ErrorDetail, Language, Limits, Receipt, SessionDescription, SessionEnd, ValidationResult } from "../frontend/types";

const limits: Limits = { hotwords_bytes: 5_000_000, upload_bytes: 1_000_000_000,
  audio_seconds: 43200, hotwords_count: 2000, context_chars: 400, speaker_min: 2, speaker_max: 100 };
const description: SessionDescription = { session_id: "session-one", phase: "editing", expires_at: "2026-10-04T12:00:00Z",
  skill_version: "0.1.2",
  audio: null, audio_error: null,
  model: "fixed-model", region: "cn-beijing", limits, audio_suffixes: [".wav"], languages: ["zh"],
  output_defaults: { json: "D:/example", document: "D:/example" }, preview: null, terminal: null };
const audio = { name: "sample.wav", size: 15, path: "D:/recordings/sample.wav" };
const words = new File(["synthetic spreadsheet"], "words.xlsx");
const receipt: Receipt = { session_id: "session-one", job_id: "job", config_path: "fixture/config.json", json_directory: "fixture/json",
  document_directory: "fixture/documents", auth_mode: "console", execution_started: false };

// 生成具备真实协议字段的合成预览。
function validation(id = "validation-1"): ValidationResult {
  return { validation_id: id, summary: { audio: { name: audio.name, path: audio.path, duration_seconds: 2,
    size_bytes: audio.size, format_name: "wav", channels: 1, sample_rate: 16000 },
    json_directory: "fixture/json",
    document_directory: "fixture/documents", warnings: [] } };
}

// 创建可控制完成时点的异步结果。
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
}
type Handler<K extends keyof Endpoints> = (payload?: object, file?: File) => Endpoints[K] | Promise<Endpoints[K]>;
type Handlers = { [K in keyof Endpoints]: Handler<K> };

// 连接前端用例与协议替身，记录请求、结束通知和视图效果。
function harness(overrides: Partial<Handlers> = {}) {
  let language: Language = "zh-CN";
  const t: Translate = (key, values) => translate(language, key, values);
  const calls: { path: keyof Endpoints; payload?: object; file?: File }[] = [];
  const view = { apiKey: "", focus: "", downloaded: false, subscriptions: 0, closed: 0 };
  let endListener: (result: SessionEnd) => void = () => undefined;
  let openListener: () => void = () => undefined;
  let errorListener: () => void = () => undefined;
  const effects: ViewEffects = {
    // 保存最后一次焦点目标。
    focus(target) { view.focus = target; },
    // 模拟凭据显示组件的私有值。
    setApiKey(value) { view.apiKey = value; },
    // 读取显示组件中的合成Key。
    getApiKey() { return view.apiKey; },
    // 记录模板已交给下载视图。
    download() { view.downloaded = true; },
  };
  const handlers: Handlers = {
    "/api/session": () => structuredClone(description),
    "/api/select-audio": () => ({ ok: true, cancelled: false, audio_id: "audio-1", name: audio.name, path: audio.path, size_bytes: audio.size }),
    "/api/import-hotwords": () => ({ name: words.name,
      rows: [{ text: "术语", weight: 4 }], warnings: [] }),
    "/api/validate": () => validation(),
    "/api/preview-ready": () => ({ ok: true }),
    "/api/api-key": () => ({ value: "" }),
    "/api/save-api-key": () => ({ ok: true }),
    "/api/select-directory": () => ({ cancelled: true }),
    "/api/cancel-picker": () => ({ ok: true }),
    "/api/edit": () => ({ ok: true, configuration: structuredClone(calls.filter(call => call.path === "/api/validate").at(-1)?.payload as Configuration),
      audio: { audio_id: "audio-1", name: audio.name, path: "D:/recordings/sample.wav", size_bytes: audio.size } }),
    ...overrides,
  };
  const api: Api = {
    // 执行对应的类型化接口替身并保存请求内容。
    async request<K extends keyof Endpoints>(path: K, payload?: object, file?: File): Promise<Endpoints[K]> {
      calls.push({ path, payload, file });
      return handlers[path](payload, file);
    },
    // 返回合成模板文件。
    async template() { return new Blob(["fixture"]); },
    // 保留单次结束通知回调，供测试控制交接时点。
    listen(ended, connected, disconnected) {
      view.subscriptions += 1;
      endListener = ended;
      openListener = connected;
      errorListener = disconnected;
      return () => { view.closed += 1; };
    },
  };
  let sequence = 0;
  const controller = useTranscription(api, effects, t, () => `request-${++sequence}`);
  return { ...controller, calls, handlers, view, t,
    // 模拟服务端发布终态。
    end(result: SessionEnd) { endListener(result); },
    // 模拟通知连接意外断开。
    disconnect() { errorListener(); },
    // 模拟浏览器自动恢复同一个事件连接。
    connected() { openListener(); },
    // 切换后续请求与界面使用的翻译语言。
    setLanguage(value: Language) { language = value; } };
}
type Page = ReturnType<typeof harness>;

// 启动会话并接收原音频选择回执。
async function addAudio(page: Page): Promise<void> {
  await page.actions.start();
  await page.actions.selectAudio();
}

// 将页面推进到已登记的只读预览。
async function preview(page: Page): Promise<void> {
  await addAudio(page);
  await page.actions.validate();
  assert.equal(page.model.phase, "preview");
  assert.equal(page.model.preview?.ready, true);
}

// 取得最近一次校验请求的配置数据。
function lastConfig(page: Page): Configuration {
  return page.calls.filter(call => call.path === "/api/validate").at(-1)?.payload as Configuration;
}

test("会话加载完成前不选文件或校验，完成后只订阅一次结束通知", async () => {
  const pending = deferred<SessionDescription>();
  const page = harness({ "/api/session": () => pending.promise });
  const starting = page.actions.start();
  await page.actions.selectAudio();
  await page.actions.validate();
  assert.deepEqual(page.calls.map(call => call.path), ["/api/session"]);
  assert.equal(page.view.subscriptions, 0);
  pending.resolve(description);
  await starting;
  assert.equal(page.view.subscriptions, 1);
  assert.equal(availability(page.model).editable, true);
  assert.equal(page.model.session?.skill_version, "0.1.2");
  page.actions.dispose();
  assert.equal(page.view.closed, 1);
});

test("已登记附件在填写页恢复，预览前无需再次选择文件", async () => {
  const selected = { audio_id: "attached-audio", name: "附件 录音.wav", path: "D:/attachments/附件 录音.wav", size_bytes: 64000 };
  const page = harness({ "/api/session": () => ({ ...description, audio: selected }) });
  await page.actions.start();
  assert.equal(page.model.phase, "editing");
  assert.deepEqual(page.model.audio, selected);
  assert.equal(page.model.preview, null);
  assert.equal(page.model.receipt, null);
  assert.equal(availability(page.model).copy, false);
  assert.deepEqual(page.calls.map(call => call.path), ["/api/session"]);
  await page.actions.validate();
  assert.equal(lastConfig(page).audio_id, selected.audio_id);
  assert.equal(page.model.phase, "preview");
  assert.deepEqual(page.calls.map(call => call.path), ["/api/session", "/api/validate", "/api/preview-ready"]);
});

test("附件错误定位音频区域，语言切换保留提示，替换成功后恢复预览", async () => {
  const diagnostic = { zh: "无法读取指定录音，请重新选择。", en: "The recording could not be read. Choose it again." };
  const page = harness({ "/api/session": () => ({ ...description, audio_error: diagnostic }) });
  await page.actions.start();
  assert.equal(page.model.phase, "editing");
  assert.deepEqual(page.model.audio, null);
  assert.equal(page.view.focus, "audio_id");
  assert.equal(page.error.value?.field, "audio_id");
  assert.equal(availability(page.model).selectAudio, true);
  const requests = page.calls.length;
  const currentError = page.error.value;
  page.setLanguage("en");
  assert.equal(page.error.value, currentError);
  assert.equal(page.error.value?.describe("en"), diagnostic.en);
  assert.equal(page.calls.length, requests);
  await page.actions.selectAudio();
  assert.equal(page.error.value, null);
  assert.deepEqual(page.model.audio, { audio_id: "audio-1", name: audio.name, path: audio.path, size_bytes: audio.size });
  await page.actions.validate();
  assert.equal(page.model.phase, "preview");
  assert.equal(page.model.preview?.ready, true);
});

test("启动失败显示不可用，事件断线保留预览并允许正常返回修改", async () => {
  const failed = harness({ "/api/session": () => { throw new Error("服务不可用"); } });
  await failed.actions.start();
  assert.equal(failed.model.phase, "unavailable");
  assert.equal(failed.error.value?.describe("zh-CN"), failed.t("unavailableHelp"));
  const page = harness();
  await preview(page);
  page.disconnect();
  assert.equal(page.model.phase, "preview");
  assert.equal(page.model.connected, false);
  assert.ok(page.model.preview);
  assert.equal(availability(page.model).copy, true);
  await page.actions.edit();
  assert.equal(page.model.phase, "editing");
  assert.equal(page.calls.some(call => call.path === "/api/edit"), true);
});

test("断线保留输入和诊断并允许本地修改，自动恢复不查询会话或提交任务", async () => {
  const page = harness();
  await addAudio(page);
  await page.actions.setAuthMode(true);
  page.view.apiKey = "unsaved-fixture-key";
  page.actions.keyChanged();
  page.actions.setContextEnabled(true);
  page.form.context = "未预览的参考文本";
  page.actions.setHotwordsEnabled(true);
  page.actions.changeHotword(page.form.hotwordRows[0].key, "text", "未预览热词");
  page.model.directories.document = "D:/selected";
  page.model.hotwords.issues = [{ key: page.form.hotwordRows[0].key, field: "weight", message: { zh: "待校对", en: "Check weight" } }];
  const before = JSON.stringify({ form: page.form, audio: page.model.audio, directories: page.model.directories, hotwords: page.model.hotwords });
  const calls = page.calls.length;
  page.disconnect();
  assert.equal(page.model.phase, "editing");
  assert.equal(page.view.apiKey, "unsaved-fixture-key");
  assert.equal(page.calls.length, calls);
  assert.equal(JSON.stringify({ form: page.form, audio: page.model.audio, directories: page.model.directories, hotwords: page.model.hotwords }), before);
  assert.equal(availability(page.model).editable, true);
  assert.equal(availability(page.model).editHotwords, true);
  assert.equal(availability(page.model).changeAuth, true);
  assert.equal(availability(page.model).importHotwords, true);
  assert.equal(availability(page.model).validate, true);
  assert.equal(page.calls.length, calls);
  page.form.context = "断线中继续填写";
  page.actions.changeHotword(page.form.hotwordRows[0].key, "text", "继续修改热词");
  page.actions.resetDirectory("document");
  page.connected();
  assert.equal(page.model.connected, true);
  assert.equal(availability(page.model).validate, true);
  assert.equal(page.form.context, "断线中继续填写");
  assert.equal(page.form.hotwordRows[0].text, "继续修改热词");
  assert.equal(page.model.directories.document, "default");
  assert.equal(page.view.apiKey, "unsaved-fixture-key");
  assert.equal(page.calls.length, calls);
  assert.equal(page.view.subscriptions, 1);
});

test("通知断线时按HTTP实际结果处理操作，失败保留输入且不自动重试", async () => {
  const page = harness({ "/api/validate": () => { throw new UiError(() => "本次请求失败"); } });
  await addAudio(page);
  page.form.context = "保留此输入";
  page.disconnect();
  page.disconnect();
  await page.actions.validate();
  assert.equal(page.model.phase, "editing");
  assert.equal(page.model.connected, false);
  assert.equal(page.form.context, "保留此输入");
  assert.equal(page.error.value?.describe("zh-CN"), "本次请求失败");
  assert.deepEqual(page.calls.map(call => call.path), ["/api/session", "/api/select-audio", "/api/validate"]);
  page.handlers["/api/validate"] = () => validation();
  await page.actions.validate();
  assert.equal(page.model.phase, "preview");
  assert.equal(page.model.connected, false);
  const calls = page.calls.length;
  page.connected();
  assert.equal(page.model.connected, true);
  assert.equal(page.calls.length, calls);
});

test("通知恢复后收到到期、取消或交接按终态收尾，迟到连接不能复活页面", async () => {
  for (const state of ["expired", "cancelled", "handed_off"] as const) {
    const page = harness();
    await preview(page);
    page.disconnect();
    const calls = page.calls.length;
    page.connected();
    page.end({ state, receipt: state === "handed_off" ? receipt : null });
    page.connected();
    page.disconnect();
    assert.equal(page.model.phase, state);
    assert.equal(page.model.preview, null);
    assert.equal(page.model.receipt?.job_id ?? null, state === "handed_off" ? receipt.job_id : null);
    assert.equal(page.view.apiKey, "");
    assert.equal(availability(page.model).validate, false);
    assert.equal(availability(page.model).copy, false);
    assert.equal(page.view.subscriptions, 1);
    assert.equal(page.calls.length, calls);
  }
});

test("预览断线后恢复同一快照与确认入口，不重做校验或预览登记", async () => {
  const page = harness();
  await preview(page);
  const snapshot = page.model.preview;
  const calls = page.calls.length;
  page.disconnect();
  assert.equal(page.model.phase, "preview");
  assert.equal(availability(page.model).copy, true);
  page.connected();
  assert.equal(page.model.preview, snapshot);
  assert.equal(availability(page.model).copy, true);
  assert.equal(page.calls.length, calls);
});

test("校验成功后进入独立预览，渲染登记成功前不能复制确认文字", async () => {
  const pending = deferred<Endpoints["/api/preview-ready"]>();
  const page = harness({ "/api/preview-ready": () => pending.promise });
  await addAudio(page);
  const validating = page.actions.validate();
  await Promise.resolve();
  await Promise.resolve();
  assert.equal(page.model.phase, "preview");
  assert.equal(availability(page.model).editable, false);
  assert.equal(availability(page.model).copy, false);
  assert.equal(page.model.receipt, null);
  pending.resolve({ ok: true });
  await validating;
  assert.equal(availability(page.model).copy, true);
  assert.deepEqual(page.calls.at(-1), { path: "/api/preview-ready", payload: { validation_id: "validation-1" }, file: undefined });
});

test("预览登记失败保留只读内容并允许返回修改，不能复制确认", async () => {
  const page = harness({ "/api/preview-ready": () => { throw new Error("登记失败"); } });
  await addAudio(page);
  await page.actions.validate();
  assert.equal(page.model.phase, "preview");
  assert.equal(page.error.value?.describe("zh-CN"), page.t("failed"));
  assert.equal(availability(page.model).copy, false);
  assert.equal(availability(page.model).edit, true);
  await page.actions.edit();
  assert.equal(page.model.phase, "editing");
});

test("返回修改等待后端批准，成功后恢复输入且没有任务编号", async () => {
  const pending = deferred<Endpoints["/api/edit"]>();
  const page = harness();
  await preview(page);
  page.handlers["/api/edit"] = () => pending.promise;
  const returning = page.actions.edit();
  await page.actions.edit();
  assert.equal(page.model.phase, "returning");
  assert.equal(availability(page.model).editable, false);
  assert.equal(availability(page.model).copy, false);
  pending.resolve({ ok: true, configuration: lastConfig(page), audio: { audio_id: "audio-1", name: audio.name, path: "D:/recordings/sample.wav", size_bytes: audio.size } });
  await returning;
  assert.equal(page.model.phase, "editing");
  assert.equal(page.model.preview, null);
  assert.equal(page.model.receipt, null);
  assert.equal(page.calls.filter(call => call.path === "/api/edit").length, 1);
  await page.actions.validate();
  assert.equal(page.model.session?.session_id, "session-one");
  assert.equal(page.model.receipt, null);
});

test("返回修改开始后忽略迟到的预览登记错误", async () => {
  const ready = deferred<Endpoints["/api/preview-ready"]>();
  const editing = deferred<Endpoints["/api/edit"]>();
  const page = harness({ "/api/preview-ready": () => ready.promise, "/api/edit": () => editing.promise });
  await addAudio(page);
  const checking = page.actions.validate();
  await Promise.resolve();
  await Promise.resolve();
  const returning = page.actions.edit();
  ready.reject(new UiError(() => "预览已退出"));
  await checking;
  assert.equal(page.model.phase, "returning");
  assert.equal(page.error.value, null);
  editing.resolve({ ok: true, configuration: lastConfig(page), audio: { audio_id: "audio-1", name: audio.name, path: "D:/recordings/sample.wav", size_bytes: audio.size } });
  await returning;
  assert.equal(page.model.phase, "editing");
  assert.equal(page.error.value, null);
});

test("返回修改被拒绝保持只读预览，直到明确终态到达", async () => {
  const page = harness({ "/api/edit": () => { throw new UiError(() => "会话已交接"); } });
  await preview(page);
  page.handlers["/api/session"] = () => ({ ...description, phase: "preview", preview: { ...validation(), configuration: lastConfig(page),
    audio: { audio_id: "audio-1", name: audio.name, path: "D:/recordings/sample.wav", size_bytes: audio.size } } });
  await page.actions.edit();
  assert.equal(page.model.phase, "preview");
  assert.equal(availability(page.model).editable, false);
  assert.equal(availability(page.model).copy, false);
  page.end({ state: "handed_off", receipt });
  assert.equal(page.model.phase, "handed_off");
  assert.deepEqual(page.model.receipt, receipt);
});

test("整单检查期间禁用输入入口并保留原表单，成功后只登记同一份预览", async () => {
  const pending = deferred<ValidationResult>();
  const page = harness({ "/api/validate": () => pending.promise });
  await addAudio(page);
  page.actions.setHotwordsEnabled(true);
  page.actions.changeHotword(page.form.hotwordRows[0].key, "text", "保留词条");
  page.actions.setContextEnabled(true);
  page.form.context = "保留参考文本";
  page.model.directories.json = "D:/chosen";
  const rows = page.form.hotwordRows;
  const row = rows[0];
  const original = configuration(page.model, page.form, limits, page.t);
  const checking = page.actions.validate();
  assert.equal(page.model.phase, "validating");
  const permissions = availability(page.model);
  for (const name of ["editable", "validate", "selectAudio", "chooseDirectory", "editHotwords", "importHotwords", "template", "changeAuth", "changeLanguage"] as const) {
    assert.equal(permissions[name], false, name);
  }
  page.actions.changeHotword(row.key, "text", "检查中不能写入");
  page.actions.removeHotword(row.key);
  page.actions.addHotword();
  page.actions.setHotwordsEnabled(false);
  page.actions.setContextEnabled(false);
  page.actions.resetDirectory("json");
  page.actions.keyChanged();
  await page.actions.selectAudio();
  await page.actions.selectDirectory("json");
  await page.actions.selectDirectory("document");
  await page.actions.importHotwords([words]);
  await page.actions.downloadTemplate();
  await page.actions.setAuthMode(true);
  assert.equal(await page.actions.saveApiKey(), false);
  await page.actions.validate();
  assert.equal(page.form.hotwordRows, rows);
  assert.equal(page.form.hotwordRows[0], row);
  assert.deepEqual(configuration(page.model, page.form, limits, page.t), original);
  assert.deepEqual(page.calls.map(call => call.path), ["/api/session", "/api/select-audio", "/api/validate"]);
  assert.equal(page.view.downloaded, false);
  assert.equal(page.model.picker, null);
  pending.resolve(validation("current"));
  await checking;
  assert.equal(page.model.phase, "preview");
  assert.equal(page.model.preview?.id, "current");
  assert.equal(page.model.preview?.ready, true);
  assert.deepEqual(page.model.preview?.configuration, original);
  assert.equal(page.calls.some(call => call.path === "/api/edit"), false);
  assert.equal(page.calls.filter(call => call.path === "/api/preview-ready").length, 1);
});

test("整单检查失败恢复原表格编辑，修正输入无需撤销不存在的预览", async () => {
  const pending = deferred<ValidationResult>();
  const page = harness({ "/api/validate": () => pending.promise });
  await addAudio(page);
  page.actions.setHotwordsEnabled(true);
  page.actions.changeHotword(page.form.hotwordRows[0].key, "text", "原热词");
  page.actions.changeHotword(page.form.hotwordRows[0].key, "weight", "9");
  const rows = page.form.hotwordRows;
  const row = rows[0];
  const checking = page.actions.validate();
  pending.reject(new UiError(() => "请修正热词。", "hotword_rows",
    [{ row: 1, field: "weight", message: { zh: "请修改权重。", en: "Correct the weight." } }]));
  await checking;
  assert.equal(page.model.phase, "editing");
  assert.equal(availability(page.model).editHotwords, true);
  assert.equal(page.form.hotwordRows, rows);
  assert.equal(page.form.hotwordRows[0], row);
  assert.equal(row.weight, "9");
  assert.equal(page.model.hotwords.issues[0].key, row.key);
  page.actions.changeHotword(row.key, "weight", "4");
  assert.equal(row.weight, "4");
  assert.deepEqual(page.model.hotwords.issues, []);
  assert.equal(page.model.preview, null);
  assert.equal(page.calls.some(call => call.path === "/api/edit"), false);
});

test("刷新只恢复服务内已校验预览，重新登记渲染且不读取Key", async () => {
  const config: Configuration = { review_enabled: false, auth_mode: "api_key", audio_id: "audio-kept", diarization_enabled: false,
    enhancement_mode: "both", hotword_rows: [{ text: "术语", weight: "4" }], context: "完整参考文本\n",
    language_hint: "en", speaker_count: null, json_directory: "D:/json", document_directory: "D:/docs" };
  const page = harness({ "/api/session": () => ({ ...description, phase: "preview", preview: { ...validation(), configuration: config,
    audio: { audio_id: "audio-kept", name: "original.wav", path: "D:/recordings/original.wav", size_bytes: 123 } } }) });
  await page.actions.start();
  assert.equal(page.model.phase, "preview");
  assert.equal(page.model.preview?.ready, true);
  assert.deepEqual(configuration(page.model, page.form, limits, page.t), config);
  assert.deepEqual(page.calls.map(call => call.path), ["/api/session", "/api/preview-ready"]);
  assert.equal(page.view.apiKey, "");
});

for (const state of ["handed_off", "expired", "cancelled"] as const) {
  test(`${state}通知结束表单、清空凭据并忽略迟到校验`, async () => {
    const pending = deferred<ValidationResult>();
    const page = harness({ "/api/validate": () => pending.promise });
    await addAudio(page);
    page.view.apiKey = "fixture-secret";
    const checking = page.actions.validate();
    page.end({ state, receipt: state === "handed_off" ? receipt : null });
    pending.resolve(validation());
    await checking;
    assert.equal(page.model.phase, state);
    assert.equal(page.model.preview, null);
    assert.equal(page.view.apiKey, "");
    assert.equal(page.view.focus, "session-ended");
    assert.equal(availability(page.model).editable, false);
    assert.equal(page.calls.some(call => call.path === "/api/preview-ready"), false);
  });
}

test("终态刷新直接恢复回执，语言切换不重新激活会话", async () => {
  const page = harness({ "/api/session": () => ({ ...description, phase: "handed_off", terminal: { state: "handed_off", receipt } }) });
  await page.actions.start();
  page.setLanguage("en");
  assert.equal(page.model.phase, "handed_off");
  assert.equal(page.view.subscriptions, 0);
  assert.deepEqual(page.model.receipt, receipt);
});

test("预览中的语言切换保持同一只读快照和已登记版本", async () => {
  const result = validation("preview-with-warning");
  result.summary.warnings = [{ zh: "转写前将合并声道。", en: "Channels will be merged before transcription." }];
  const page = harness({ "/api/validate": () => result });
  await preview(page);
  const count = page.calls.length;
  const snapshot = page.model.preview;
  page.setLanguage("en");
  assert.equal(page.model.phase, "preview");
  assert.equal(page.model.preview?.ready, true);
  assert.equal(page.model.preview, snapshot);
  assert.equal(page.model.preview?.id, "preview-with-warning");
  assert.equal(localize(page.model.preview!.summary.warnings[0], "en"), "Channels will be merged before transcription.");
  assert.equal(page.calls.length, count);
  assert.equal(page.t("confirmationMessage", { id: "session-one", model: "qwen-audio-3.1-asr-flash-filetrans" }),
    "Confirm sending the recording in this preview to Alibaba Cloud Model Studio in the Beijing region for transcription with qwen-audio-3.1-asr-flash-filetrans. Editing session ID: session-one");
});

test("修改热词与上下文和切换语言只更新本地输入，最终点击一次检查", async () => {
  const page = harness();
  await addAudio(page);
  const before = page.calls.length;
  page.form.hotwordsEnabled = true;
  page.form.contextEnabled = true;
  page.actions.addHotword();
  page.actions.changeHotword(page.form.hotwordRows[0].key, "text", "术语");
  page.form.context = "完整参考文本";
  page.actions.changed();
  page.setLanguage("en");
  assert.equal(page.calls.length, before);
  assert.deepEqual(page.model.hotwords.issues, []);
  assert.equal(page.error.value, null);
  await page.actions.validate();
  assert.equal(page.calls.filter(call => call.path === "/api/validate").length, 1);
  assert.deepEqual(lastConfig(page).hotword_rows, [{ text: "术语", weight: 4 }]);
  assert.equal(lastConfig(page).context, "完整参考文本");
});

test("切换语言呈现已有错误的对应翻译，输入和检查次数保持不变", async () => {
  const issues: ErrorDetail[] = [{ row: 1, field: "weight", message: { zh: "请修改权重。", en: "Correct the weight." } }];
  const page = harness({ "/api/import-hotwords": () => ({ name: words.name,
    rows: [{ text: "术语", weight: 9 }], warnings: [] }),
    "/api/validate": () => { throw new UiError({ zh: "请修正热词。", en: "Correct the hotword list." }, "hotword_rows", issues); } });
  await addAudio(page);
  page.form.hotwordsEnabled = true;
  await page.actions.importHotwords([words]);
  assert.deepEqual(page.model.hotwords.issues, []);
  await page.actions.validate();
  const before = page.calls.length;
  const row = page.form.hotwordRows[0];
  const recorded = page.model.hotwords.issues[0] as EditorIssue;
  const issue = page.error.value;
  assert.equal(issue?.describe("zh-CN"), "请修正热词。");
  page.setLanguage("en");
  assert.equal(page.error.value, issue);
  assert.equal(issue?.describe("en"), "Correct the hotword list.");
  assert.equal(localize(recorded.message, "en"), "Correct the weight.");
  assert.equal(recorded.key, row.key);
  assert.equal(page.form.hotwordRows[0], row);
  assert.equal(page.model.hotwords.issues[0], recorded);
  assert.equal(page.calls.length, before);
  page.actions.changeHotword(page.form.hotwordRows[0].key, "weight", "4");
  assert.deepEqual(page.model.hotwords.issues, []);
  assert.equal(page.calls.length, before);
  page.handlers["/api/validate"] = () => validation();
  await page.actions.validate();
  assert.equal(page.model.phase, "preview");
});

test("未选择音频定位文件选择区，空增强输入由整单接口检查并保留原文", async () => {
  const page = harness();
  await page.actions.start();
  await page.actions.validate();
  assert.equal(page.error.value?.field, "audio_id");
  await page.actions.selectAudio();
  page.form.hotwordsEnabled = true;
  page.handlers["/api/validate"] = () => { throw new UiError(() => "请添加热词。", "hotword_rows"); };
  await page.actions.validate();
  assert.equal(page.error.value?.field, "hotword_rows");
  page.form.hotwordsEnabled = false;
  page.form.contextEnabled = true;
  page.form.context = " \n\t";
  page.handlers["/api/validate"] = () => { throw new UiError(() => "内容仅包含空白，共3个字符。", "context"); };
  await page.actions.validate();
  assert.equal(page.form.context, " \n\t");
  assert.equal(page.view.focus, "context");
  assert.equal(page.error.value?.message, "内容仅包含空白，共3个字符。");
  assert.equal(lastConfig(page).context, " \n\t");
  assert.equal(page.calls.filter(call => call.path === "/api/validate").length, 2);
});

test("超长上下文原样发送后显示服务器错误，关闭说话人区分忽略旧人数", async () => {
  const page = harness({ "/api/session": () => ({ ...description, limits: { ...limits, speaker_max: 4, context_chars: 3 } }) });
  await addAudio(page);
  page.form.speaker = "1e";
  await page.actions.validate();
  assert.equal(page.error.value?.field, "speaker_count");
  page.form.diarizationEnabled = false;
  page.form.contextEnabled = true;
  page.form.context = "甲乙丙丁";
  page.handlers["/api/validate"] = () => { throw new UiError(() => "参考文本超出1个字符。", "context"); };
  page.actions.changed("speaker_count");
  assert.equal(Boolean(page.error.value), false);
  await page.actions.validate();
  assert.equal(lastConfig(page).context, "甲乙丙丁");
  assert.equal(page.error.value?.message, "参考文本超出1个字符。");
  assert.equal(page.form.context, "甲乙丙丁");
  page.form.context = "甲乙";
  page.actions.changed("context");
  assert.equal(page.error.value, null);
  page.handlers["/api/validate"] = () => validation();
  await page.actions.validate();
  assert.equal(lastConfig(page).speaker_count, null);
});

test("音频选择只发送窗口编号，取消或失败保留已选择的原文件", async () => {
  const page = harness();
  await addAudio(page);
  const selected = page.model.audio;
  const first = page.calls.find(call => call.path === "/api/select-audio");
  assert.deepEqual(first?.payload, { picker_id: "request-1" });
  assert.equal(first?.file, undefined);
  assert.equal(page.model.audio?.path, audio.path);
  page.handlers["/api/select-audio"] = () => ({ cancelled: true });
  await page.actions.selectAudio();
  assert.deepEqual(page.model.audio, selected);
  page.handlers["/api/select-audio"] = () => { throw new Error("选择窗口不可用"); };
  await page.actions.selectAudio();
  assert.deepEqual(page.model.audio, selected);
  assert.equal(page.error.value?.field, "audio_id");
  assert.equal(page.model.picker, null);
  assert.equal(page.calls.filter(call => call.path === "/api/select-audio").length, 3);
});

test("音频窗口等待时阻止第二个窗口，用同一编号取消并忽略结束后的结果", async () => {
  const pending = deferred<Endpoints["/api/select-audio"]>();
  const page = harness({ "/api/select-audio": () => pending.promise });
  await page.actions.start();
  const selecting = page.actions.selectAudio();
  await page.actions.selectAudio();
  await page.actions.selectDirectory("json");
  assert.equal(availability(page.model).validate, false);
  await page.actions.cancelPicker();
  assert.deepEqual(page.calls.at(-1)?.payload, { picker_id: "request-1" });
  assert.equal(page.calls.at(-1)?.path, "/api/cancel-picker");
  page.end({ state: "cancelled", receipt: null });
  pending.resolve({ ok: true, cancelled: false, audio_id: "late", name: audio.name, path: audio.path, size_bytes: audio.size });
  await selecting;
  assert.equal(page.model.audio, null);
  assert.equal(page.calls.filter(call => call.path === "/api/select-audio").length, 1);
});

test("Excel类型与大小使用会话限制，导入失败不自动重试", async () => {
  const page = harness({ "/api/session": () => ({ ...description, limits: { ...limits, hotwords_bytes: 10 } }),
    "/api/import-hotwords": () => { throw new Error("Excel读取失败"); } });
  await page.actions.start();
  await page.actions.importHotwords([new File(["a"], "words.csv")]);
  await page.actions.importHotwords([new File(["12345678901"], "words.xlsx")]);
  assert.equal(page.calls.filter(call => call.path === "/api/import-hotwords").length, 0);
  await page.actions.importHotwords([new File(["a"], "words.XLSX")]);
  assert.equal(page.model.hotwordImport.status, "failed");
  assert.equal(page.calls.filter(call => call.path === "/api/import-hotwords").length, 1);
});

test("目录等待保留其他编辑能力，取消沿用原编号，选定后可恢复默认", async () => {
  const pending = deferred<Endpoints["/api/select-directory"]>();
  const page = harness({ "/api/select-directory": () => pending.promise });
  await addAudio(page);
  const selecting = page.actions.selectDirectory("json");
  page.form.speaker = "4";
  page.actions.changed();
  await page.actions.cancelPicker();
  assert.equal(availability(page.model).editable, true);
  assert.equal(availability(page.model).chooseDirectory, false);
  const opening = page.calls.find(call => call.path === "/api/select-directory")?.payload as { picker_id: string };
  assert.equal((page.calls.at(-1)?.payload as { picker_id: string }).picker_id, opening.picker_id);
  pending.resolve({ cancelled: true });
  await selecting;
  page.handlers["/api/select-directory"] = () => ({ cancelled: false, path: "D:/chosen" });
  await page.actions.selectDirectory("json");
  assert.equal(page.model.directories.json, "D:/chosen");
  page.actions.resetDirectory("json");
  await page.actions.validate();
  assert.equal(lastConfig(page).json_directory, "default");
  assert.equal(lastConfig(page).speaker_count, 4);
});

test("已有Key只进入局部组件，预览清空显示，返回编辑才重新读取", async () => {
  const page = harness({ "/api/api-key": () => ({ value: "fixture-key" }) });
  await addAudio(page);
  await page.actions.setAuthMode(true);
  assert.equal(page.view.apiKey, "fixture-key");
  await page.actions.validate();
  assert.equal(page.view.apiKey, "");
  assert.equal(JSON.stringify(page.model).includes("fixture-key"), false);
  assert.equal(JSON.stringify(page.form).includes("fixture-key"), false);
  assert.equal(page.calls.some(call => call.path === "/api/save-api-key"), false);
  await page.actions.edit();
  assert.equal(page.view.apiKey, "fixture-key");
  assert.equal(page.calls.filter(call => call.path === "/api/api-key").length, 2);
});

test("模式切换与结束使迟到Key读取失效", async () => {
  const pending = deferred<{ value: string }>();
  const page = harness({ "/api/api-key": () => pending.promise });
  await addAudio(page);
  const loading = page.actions.setAuthMode(true);
  await page.actions.setAuthMode(false);
  pending.resolve({ value: "fixture-key" });
  await loading;
  assert.equal(page.view.apiKey, "");
  assert.equal(page.model.auth.status, "idle");
});

test("无音频可单独保存Key，保存中禁止重复请求与模式切换", async () => {
  const pending = deferred<Endpoints["/api/save-api-key"]>();
  const page = harness({ "/api/save-api-key": () => pending.promise });
  await page.actions.start();
  await page.actions.setAuthMode(true);
  page.view.apiKey = "fixture-key";
  page.actions.keyChanged();
  const saving = page.actions.saveApiKey();
  assert.equal(await page.actions.saveApiKey(), false);
  await page.actions.setAuthMode(false);
  await page.actions.validate();
  assert.equal(page.form.useApiKey, true);
  pending.resolve({ ok: true });
  assert.equal(await saving, true);
  assert.equal(page.model.phase, "editing");
  assert.equal(page.model.receipt, null);
  assert.deepEqual(page.calls.map(call => call.path), ["/api/session", "/api/api-key", "/api/save-api-key"]);
});

test("填写Key后先保存再预览，Key不进入任务输入", async () => {
  const page = harness();
  await addAudio(page);
  await page.actions.setAuthMode(true);
  page.view.apiKey = "fixture-new-key";
  page.actions.keyChanged();
  await page.actions.validate();
  assert.deepEqual(page.calls.slice(-3).map(call => call.path), ["/api/save-api-key", "/api/validate", "/api/preview-ready"]);
  assert.equal(lastConfig(page).auth_mode, "api_key");
  assert.equal(JSON.stringify(lastConfig(page)).includes("fixture-new-key"), false);
});

test("Key保存期间其他字段改变，保存错误仍指向Key且保留输入", async () => {
  const pending = deferred<Endpoints["/api/save-api-key"]>();
  const page = harness({ "/api/save-api-key": () => pending.promise });
  await addAudio(page);
  await page.actions.setAuthMode(true);
  page.view.apiKey = "fixture invalid key";
  page.actions.keyChanged();
  const saving = page.actions.saveApiKey();
  assert.equal(availability(page.model).editable, true);
  page.actions.setContextEnabled(true);
  page.form.context = "独立保存Key时仍可填写";
  page.form.diarizationEnabled = false;
  page.actions.changed();
  pending.reject(new UiError(() => "Key含有空白，请修正。", "auth_mode"));
  assert.equal(await saving, false);
  assert.equal(page.model.phase, "editing");
  assert.equal(page.model.auth.status, "failed");
  assert.equal(page.error.value?.field, "auth_mode");
  assert.equal(page.view.focus, "auth_mode");
  assert.equal(page.view.apiKey, "fixture invalid key");
  assert.equal(page.form.context, "独立保存Key时仍可填写");
  assert.equal(page.calls.some(call => call.path === "/api/validate"), false);
  page.view.apiKey = "fixture-corrected-key";
  page.actions.keyChanged();
  page.handlers["/api/save-api-key"] = () => ({ ok: true });
  await page.actions.validate();
  assert.equal(lastConfig(page).diarization_enabled, false);
  assert.equal(page.model.phase, "preview");
});

test("整单检查自动保存Key时持续禁用表单，保存后直接检查同一份设置", async () => {
  const pending = deferred<Endpoints["/api/save-api-key"]>();
  const page = harness({ "/api/save-api-key": () => pending.promise });
  await addAudio(page);
  await page.actions.setAuthMode(true);
  page.view.apiKey = "fixture-key";
  page.actions.keyChanged();
  const checking = page.actions.validate();
  assert.equal(page.model.phase, "validating");
  assert.equal(availability(page.model).editable, false);
  assert.equal(availability(page.model).changeAuth, false);
  page.actions.setContextEnabled(true);
  await page.actions.setAuthMode(false);
  page.actions.keyChanged();
  assert.equal(page.form.contextEnabled, false);
  assert.equal(page.form.useApiKey, true);
  assert.equal(page.model.auth.status, "saving");
  pending.resolve({ ok: true });
  await checking;
  assert.equal(page.model.phase, "preview");
  assert.equal(page.model.auth.status, "ready");
  assert.equal(page.calls.filter(call => call.path === "/api/save-api-key").length, 1);
  assert.equal(page.calls.filter(call => call.path === "/api/validate").length, 1);
  assert.equal(page.calls.filter(call => call.path === "/api/preview-ready").length, 1);
  assert.equal(page.calls.some(call => call.path === "/api/edit"), false);
  assert.equal(lastConfig(page).diarization_enabled, true);
});

test("空Key阻止预览，切回控制台可继续", async () => {
  const page = harness();
  await addAudio(page);
  await page.actions.setAuthMode(true);
  await page.actions.validate();
  assert.equal(page.error.value?.field, "auth_mode");
  await page.actions.setAuthMode(false);
  await page.actions.validate();
  assert.equal(page.model.phase, "preview");
});

test("导入数组保留错误值，显示序号从1开始且不发送内部key或row", async () => {
  const rows = [{ text: 100, weight: 8 }, { text: "合法术语", weight: 4 }];
  const page = harness({ "/api/import-hotwords": () => ({ name: words.name, rows, warnings: [] }) });
  await addAudio(page);
  page.form.hotwordsEnabled = true;
  await page.actions.importHotwords([words]);
  assert.deepEqual(page.form.hotwordRows.map(row => row.row), [1, 2]);
  assert.deepEqual(hotwordRows(page.form), rows);
  assert.deepEqual(page.model.hotwords.issues, []);
  const before = page.calls.length;
  page.actions.changeHotword(page.form.hotwordRows[0].key, "text", "修改后的术语");
  assert.equal(page.calls.length, before);
  await page.actions.validate();
  assert.deepEqual(lastConfig(page).hotword_rows, [{ text: "修改后的术语", weight: 8 }, rows[1]]);
});

test("删除与新增后序号重排，未删除词条的组件key保持稳定", async () => {
  const page = harness();
  await addAudio(page);
  page.form.hotwordsEnabled = true;
  page.actions.addHotword();
  page.actions.changeHotword(1, "text", "甲词");
  page.actions.addHotword();
  page.actions.changeHotword(2, "text", "乙词");
  page.actions.removeHotword(1);
  page.actions.addHotword();
  page.actions.changeHotword(3, "text", "丙词");
  assert.deepEqual(page.form.hotwordRows.map(row => [row.key, row.row]), [[2, 1], [3, 2]]);
  await page.actions.validate();
  assert.deepEqual(lastConfig(page).hotword_rows, [{ text: "乙词", weight: 4 }, { text: "丙词", weight: 4 }]);
});

test("编辑导入异常单元格只清除该格类型标记", async () => {
  const page = harness({ "/api/import-hotwords": () => ({ name: words.name,
    rows: [{ text: "2026-10-03", weight: "#N/A", invalid_fields: ["text", "weight"] }], warnings: [] }) });
  await page.actions.start();
  await page.actions.importHotwords([words]);
  page.actions.changeHotword(1, "text", "技术术语");
  assert.deepEqual(page.form.hotwordRows[0].invalid_fields, ["weight"]);
  page.actions.changeHotword(1, "weight", "4");
  assert.equal(page.form.hotwordRows[0].invalid_fields, undefined);
});

test("最终校验错误交给同一表格，导入失败保留已填词条", async () => {
  const detail: ErrorDetail = { row: 1, field: "weight", message: { zh: "请修改权重。", en: "Correct the weight." } };
  const page = harness({ "/api/validate": () => { throw new UiError(() => "请修正热词。", "hotword_rows", [detail]); },
    "/api/import-hotwords": () => { throw new UiError({ zh: "当前 Excel 未按模板导入。", en: "Use the Excel template." }, "hotword_rows"); } });
  await addAudio(page);
  page.form.hotwordsEnabled = true;
  page.actions.addHotword();
  page.actions.changeHotword(1, "text", "原有词条");
  await page.actions.validate();
  const row = page.form.hotwordRows[0];
  const issues = page.model.hotwords.issues;
  assert.deepEqual(issues.map(issue => [issue.key, issue.field, issue.message]), [[row.key, detail.field, detail.message]]);
  assert.equal(page.view.focus, "hotword_rows");
  await page.actions.importHotwords([words]);
  assert.equal(page.form.hotwordRows[0].text, "原有词条");
  assert.equal(page.form.hotwordRows[0], row);
  assert.equal(page.model.hotwords.issues, issues);
  assert.equal(page.error.value?.describe("en"), "Use the Excel template.");
});

test("编辑一个单元格仅移除该格错误，其他区域变化保留词表检查结果", async () => {
  const details: ErrorDetail[] = [
    { row: 1, field: "text", message: { zh: "请填写热词。", en: "Enter a hotword." } },
    { row: 1, field: "weight", message: { zh: "请修改权重。", en: "Correct the weight." } },
    { row: 2, field: "weight", message: { zh: "请修改权重。", en: "Correct the weight." } },
  ];
  const page = harness({ "/api/import-hotwords": () => ({ name: words.name,
    rows: [{ text: "", weight: 9 }, { text: "另一热词", weight: 8 }], warnings: [] }),
    "/api/validate": () => { throw new UiError(() => "请修改热词表。", "hotword_rows", details); } });
  await addAudio(page);
  page.actions.setHotwordsEnabled(true);
  await page.actions.importHotwords([words]);
  await page.actions.validate();
  const [first, second] = page.form.hotwordRows;
  const count = page.calls.length;
  const currentError = page.error.value;
  page.form.context = "保留词表错误的普通修改";
  page.actions.changed("context");
  page.form.diarizationEnabled = false;
  page.actions.changed("speaker_count");
  assert.equal(page.error.value, currentError);
  assert.equal(page.model.hotwords.issues.length, 3);
  page.actions.changeHotword(first.key, "weight", "4");
  assert.deepEqual(page.model.hotwords.issues.map(issue => [issue.key, issue.field]), [[first.key, "text"], [second.key, "weight"]]);
  page.actions.addHotword();
  assert.equal(page.model.hotwords.issues.length, 2);
  assert.equal(page.calls.length, count);
});

test("再次明确检查替换旧词表诊断，上下文失败时保留数据而不保留已解决的红标", async () => {
  const warning = { zh: "仅读取热词工作表。", en: "Only the hotword sheet is used." };
  const rows = Array.from({ length: 51 }, (_, index) => ({ text: `term${index}`, weight: 50 }));
  const page = harness({
    "/api/import-hotwords": () => ({ name: words.name, rows, warnings: [warning] }),
    "/api/validate": () => { throw new UiError(() => "超级热词超过上限。", "hotword_rows",
      [{ row: 51, field: "weight", message: { zh: "超级热词最多50个。", en: "Up to 50 super hotwords." } }]); },
  });
  await addAudio(page);
  page.actions.setHotwordsEnabled(true);
  page.actions.setContextEnabled(true);
  await page.actions.importHotwords([words]);
  await page.actions.validate();
  assert.equal(page.model.hotwords.issues[0].row, 51);
  const currentRows = page.form.hotwordRows;
  const keys = currentRows.map(row => row.key);
  const imported = page.model.hotwordImport;
  const warnings = page.model.hotwords.warnings;
  page.actions.changeHotword(currentRows[0].key, "weight", "4");
  assert.equal(page.model.hotwords.issues[0].row, 51);
  assert.equal(page.calls.filter(call => call.path === "/api/validate").length, 1);
  page.handlers["/api/validate"] = () => {
    throw new UiError({ zh: "上下文为空。", en: "Context is empty." }, "context");
  };
  await page.actions.validate();
  assert.equal(page.model.phase, "editing");
  assert.equal(page.error.value?.field, "context");
  assert.deepEqual(page.model.hotwords.issues, []);
  assert.equal(page.form.hotwordRows, currentRows);
  assert.deepEqual(currentRows.map(row => row.key), keys);
  assert.equal(currentRows[0].weight, "4");
  assert.equal(currentRows[50].weight, 50);
  assert.equal(page.model.hotwordImport, imported);
  assert.equal(imported.status, "ready");
  assert.equal(page.model.hotwords.warnings, warnings);
  assert.deepEqual(warnings, [warning]);
  assert.equal(page.calls.filter(call => call.path === "/api/validate").length, 2);
});

test("删除后错误跟随原词条稳定标识，显示行号从一重排", async () => {
  const page = harness({ "/api/import-hotwords": () => ({ name: words.name,
    rows: [{ text: "首词", weight: 4 }, { text: "第二词", weight: 4 }, { text: "保留错误", weight: 9 }], warnings: [] }),
    "/api/validate": () => { throw new UiError(() => "请修改热词表。", "hotword_rows",
      [{ row: 3, field: "weight", message: { zh: "请修改权重。", en: "Correct the weight." } }]); } });
  await addAudio(page);
  page.actions.setHotwordsEnabled(true);
  await page.actions.importHotwords([words]);
  await page.actions.validate();
  const [first, second, third] = page.form.hotwordRows;
  page.actions.removeHotword(first.key);
  assert.deepEqual(page.form.hotwordRows.map(row => [row.key, row.row]), [[second.key, 1], [third.key, 2]]);
  assert.equal(page.model.hotwords.issues[0].key, third.key);
  assert.equal(page.model.hotwords.issues[0].row, 3);
  page.actions.changeHotword(second.key, "weight", "5");
  assert.equal(page.model.hotwords.issues[0].key, third.key);
});

for (const change of ["text", "remove"] as const) {
  test(`${change}两条重复词中的一条后清除重复提示，其他行的错误保留`, async () => {
    const duplicate = { zh: "存在重复数据，请保留至一行", en: "Duplicate entries. Keep one row." };
    const details: ErrorDetail[] = [
      { row: 1, field: "text", duplicate_group: 1, message: duplicate },
      { row: 2, field: "text", duplicate_group: 1, message: duplicate },
      { row: 3, field: "weight", message: { zh: "请修改权重。", en: "Correct the weight." } },
    ];
    const page = harness({ "/api/import-hotwords": () => ({ name: words.name,
      rows: [{ text: "IPO", weight: 4 }, { text: "IPO", weight: 5 }, { text: "其他词", weight: 9 }], warnings: [] }),
      "/api/validate": () => { throw new UiError(() => "请修改热词表。", "hotword_rows", details); } });
    await addAudio(page);
    page.actions.setHotwordsEnabled(true);
    await page.actions.importHotwords([words]);
    await page.actions.validate();
    const [first, , third] = page.form.hotwordRows;
    assert.equal(page.model.hotwords.issues[0].duplicate_group, 1);
    assert.equal(page.model.hotwords.issues[1].duplicate_group, 1);
    page.actions.changeHotword(first.key, "weight", "3");
    assert.equal(page.model.hotwords.issues.length, 3);
    if (change === "text") page.actions.changeHotword(first.key, "text", "新词");
    else page.actions.removeHotword(first.key);
    assert.deepEqual(page.model.hotwords.issues.map(issue => [issue.key, issue.field]), [[third.key, "weight"]]);
    assert.equal(page.calls.filter(call => call.path === "/api/validate").length, 1);
  });
}

for (const count of [3, 4]) {
  test(`${count}个重复词连续删除时剩余重复行保持错误，直到仅剩一行`, async () => {
    const duplicate = { zh: "存在重复数据，请保留至一行", en: "Duplicate entries. Keep only one row." };
    const rows = [...Array.from({ length: count }, () => ({ text: "IPO", weight: 4 })), { text: "保留权重问题", weight: 9 }];
    const details: ErrorDetail[] = [
      ...Array.from({ length: count }, (_, index) => ({ row: index + 1, field: "text", duplicate_group: 1, message: duplicate })),
      { row: count + 1, field: "weight", message: { zh: "请修改权重。", en: "Correct the weight." } },
    ];
    const page = harness({ "/api/import-hotwords": () => ({ name: words.name, rows, warnings: [] }),
      "/api/validate": () => { throw new UiError(() => "请修改热词表。", "hotword_rows", details); } });
    await addAudio(page);
    page.actions.setHotwordsEnabled(true);
    await page.actions.importHotwords([words]);
    await page.actions.validate();
    const duplicateKeys = page.form.hotwordRows.slice(0, count).map(row => row.key);
    const weightKey = page.form.hotwordRows[count].key;
    while (duplicateKeys.length > 1) {
      page.actions.removeHotword(duplicateKeys.shift()!);
      assert.deepEqual(page.model.hotwords.issues.filter(issue => issue.duplicate_group === 1).map(issue => issue.key),
        duplicateKeys.length >= 2 ? duplicateKeys : []);
      assert.equal(page.model.hotwords.issues.some(issue => issue.key === weightKey && issue.field === "weight"), true);
      assert.deepEqual(page.form.hotwordRows.map(row => row.row), Array.from({ length: duplicateKeys.length + 1 }, (_, index) => index + 1));
      assert.equal(page.error.value?.field, "hotword_rows");
    }
    assert.equal(page.calls.filter(call => call.path === "/api/validate").length, 1);
  });
}

test("修改三个重复词之一保留剩余重复对，修改权重保持重复提示", async () => {
  const duplicate = { zh: "存在重复数据，请保留至一行", en: "Duplicate entries. Keep only one row." };
  const details: ErrorDetail[] = [
    ...[1, 2, 3].map(row => ({ row, field: "text", duplicate_group: 1, message: duplicate })),
    { row: 3, field: "weight", message: { zh: "请修改权重。", en: "Correct the weight." } },
    { row: 4, field: "weight", message: { zh: "请修改权重。", en: "Correct the weight." } },
  ];
  const page = harness({ "/api/import-hotwords": () => ({ name: words.name,
    rows: [{ text: "IPO", weight: 4 }, { text: "IPO", weight: 4 }, { text: "IPO", weight: 9 }, { text: "其他词", weight: 9 }], warnings: [] }),
    "/api/validate": () => { throw new UiError(() => "请修改热词表。", "hotword_rows", details); } });
  await addAudio(page);
  page.actions.setHotwordsEnabled(true);
  await page.actions.importHotwords([words]);
  await page.actions.validate();
  const [first, second, third, fourth] = page.form.hotwordRows;
  page.actions.changeHotword(third.key, "weight", "4");
  assert.deepEqual(page.model.hotwords.issues.filter(issue => issue.duplicate_group === 1).map(issue => issue.key),
    [first.key, second.key, third.key]);
  page.actions.changeHotword(first.key, "text", "改后的第一个词");
  assert.deepEqual(page.model.hotwords.issues.filter(issue => issue.duplicate_group === 1).map(issue => issue.key), [second.key, third.key]);
  assert.equal(page.model.hotwords.issues.some(issue => issue.key === fourth.key && issue.field === "weight"), true);
  page.actions.changeHotword(second.key, "text", "改后的第二个词");
  assert.deepEqual(page.model.hotwords.issues.map(issue => [issue.key, issue.field]), [[fourth.key, "weight"]]);
  assert.equal(page.calls.filter(call => call.path === "/api/validate").length, 1);
});

test("关闭增强清空对应输入和提示，保留另一增强区域与已保存Key", async () => {
  const page = harness({ "/api/api-key": () => ({ value: "fixture-kept-key" }),
    "/api/validate": () => { throw new UiError({ zh: "上下文过长。", en: "Context is too long." }, "context"); } });
  await addAudio(page);
  await page.actions.setAuthMode(true);
  page.actions.setHotwordsEnabled(true);
  assert.deepEqual(hotwordRows(page.form), [{ text: "", weight: 4 }]);
  await page.actions.importHotwords([words]);
  page.actions.setContextEnabled(true);
  page.form.context = "待清理参考文本";
  await page.actions.validate();
  const keyState = { ...page.model.auth };
  const requests = page.calls.length;
  page.actions.setHotwordsEnabled(false);
  assert.deepEqual(page.form.hotwordRows, []);
  assert.equal(page.model.hotwordImport.status, "empty");
  assert.equal(page.model.hotwordImport.name, "");
  assert.deepEqual(page.model.hotwords, { issues: [], warnings: [] });
  assert.equal(page.form.context, "待清理参考文本");
  assert.equal(page.error.value?.field, "context");
  page.actions.setContextEnabled(false);
  assert.equal(page.form.context, "");
  assert.equal(page.error.value, null);
  page.actions.setHotwordsEnabled(true);
  page.actions.setContextEnabled(true);
  assert.deepEqual(hotwordRows(page.form), [{ text: "", weight: 4 }]);
  assert.equal(page.form.context, "");
  assert.equal(page.form.useApiKey, true);
  assert.equal(page.view.apiKey, "fixture-kept-key");
  assert.deepEqual(page.model.auth, keyState);
  assert.equal(page.calls.length, requests);
});

test("热词和上下文共同传输，特殊字符原样保存，关闭增强排除旧值", async () => {
  const page = harness();
  await addAudio(page);
  page.form.hotwordsEnabled = true;
  page.form.contextEnabled = true;
  page.actions.addHotword();
  page.actions.changeHotword(1, "text", "特殊 & 词");
  page.form.context = '--help a=b "中文"\r\nC:\\voice files\\\t😀𠮷 cafe\u0301 $HOME &|<>^%! `文本`';
  await page.actions.validate();
  assert.equal(lastConfig(page).enhancement_mode, "both");
  assert.equal(lastConfig(page).context, page.form.context);
  await page.actions.edit();
  page.actions.setHotwordsEnabled(false);
  page.actions.setContextEnabled(false);
  assert.deepEqual(page.form.hotwordRows, []);
  assert.equal(page.form.context, "");
  await page.actions.validate();
  assert.deepEqual(lastConfig(page).hotword_rows, []);
  assert.equal(lastConfig(page).context, "");
});

test("HTTP使用同源cookie与语言头，保留服务端字段错误", async () => {
  let sent: RequestInit | undefined;
  const t: Translate = (key, values) => translate("en", key, values);
  const api = createApi(async (_url, init) => { sent = init;
    return new Response(JSON.stringify({ error: { zh: "上下文无效", en: "Invalid context" }, field: "context" }), { status: 422 }); }, () => "en", t);
  await assert.rejects(api.request("/api/validate", { context: "a\n'\\中文" }),
    (reason: unknown) => reason instanceof UiError && reason.field === "context" && reason.describe("en") === "Invalid context");
  assert.equal(sent?.credentials, "same-origin");
  assert.equal(new Headers(sent?.headers).get("Accept-Language"), "en");
  assert.equal(new Headers(sent?.headers).has("X-ASR-Token"), false);
  assert.equal(JSON.parse(sent?.body as string).context, "a\n'\\中文");
});

test("通知断线保留原生重连，恢复仅通知页面，终态后关闭且忽略迟到回调", () => {
  let listener: EventListener = () => undefined;
  let closed = 0;
  let opened = 0;
  let ended: SessionEnd | null = null;
  let disconnected = 0;
  let connected = 0;
  const source = { onopen: null as (() => void) | null, onerror: null as (() => void) | null,
    // 记录结束事件回调。
    addEventListener(name: string, callback: EventListener) { assert.equal(name, "ended"); listener = callback; },
    // 记录连接关闭。
    close() { closed += 1; } };
  const t: Translate = (key, values) => translate("en", key, values);
  const api = createApi(fetch, () => "en", t, url => { opened += 1; assert.equal(url, "/api/events"); return source as unknown as EventSource; });
  const stop = api.listen(result => { ended = result; }, () => { connected += 1; }, () => { disconnected += 1; });
  const lateOpen = source.onopen;
  const lateError = source.onerror;
  source.onopen?.();
  source.onerror?.();
  assert.equal(closed, 0);
  assert.equal(disconnected, 1);
  source.onopen?.();
  assert.equal(connected, 2);
  listener(new MessageEvent("ended", { data: JSON.stringify({ state: "expired", receipt: null }) }));
  assert.deepEqual(ended, { state: "expired", receipt: null });
  assert.equal(closed, 1);
  lateOpen?.();
  lateError?.();
  stop();
  assert.equal(source.onopen, null);
  assert.equal(source.onerror, null);
  assert.equal(connected, 2);
  assert.equal(disconnected, 1);
  assert.equal(closed, 1);
  assert.equal(opened, 1);
});

test("目录选择保留普通编辑能力，等待期间阻止整单校验", () => {
  const model = createModel();
  model.phase = "editing";
  assert.equal(availability(model).validate, true);
  assert.equal(availability(model).importHotwords, true);
  model.picker = { id: "picker", kind: "json", cancelling: false };
  assert.equal(availability(model).editable, true);
  assert.equal(availability(model).validate, false);
});


// 创建只含合成文本的回听会话，不读取音频或调用云端。
function reviewHarness() {
  const initial: ReviewDocument = { job_id: "synthetic-review", skill_version: "0.1.5", model: "synthetic",
    source_name: "synthetic.wav", revision: 0, closed: false, delivery: null, export_revision: null,
    audio: { available: true, name: "synthetic.wav", kind: "original", error: null },
    sentences: [{ index: 1, begin_ms: 0, end_ms: 1000, text: "原句", speaker_id: 0, original_text: "原句", original_speaker_id: 0 },
      { index: 2, begin_ms: 1000, end_ms: 2000, text: "第二句", speaker_id: null, original_text: "第二句", original_speaker_id: null }], speakers: [{ id: 0, name: "" }] };
  const calls: { path: keyof ReviewEndpoints; payload?: object }[] = [];
  let revision = 0;
  const handlers: { save?: (payload: object) => Promise<{ revision: number }>;
    export?: () => Promise<ReviewEndpoints["/api/review/export"]>;
    selectAudio?: () => Promise<ReviewEndpoints["/api/review/select-audio"]>; cancelled?: boolean } = {};
  const presence = { opened: 0, closed: 0 };
  const api: ReviewApi = {
    // 记录在场连接，不在测试中创建真实浏览器连接。
    presence(connected) { presence.opened += 1; connected(); return () => { presence.closed += 1; }; },
    // 模拟保存、重选与导出回执，并记录真实提交顺序。
    async request<K extends keyof ReviewEndpoints>(path: K, payload?: object): Promise<ReviewEndpoints[K]> {
      calls.push({ path, payload: payload ? structuredClone(payload) : undefined });
      let result: unknown;
      if (path === "/api/review") result = structuredClone(initial);
      else if (path === "/api/review/save") result = handlers.save ? await handlers.save(payload!) : { revision: ++revision };
      else if (path === "/api/review/export") result = handlers.export ? await handlers.export()
        : handlers.cancelled ? { cancelled: true } : { cancelled: false, export_revision: revision, delivery: { status: "COMPLETE", files: {}, message: "synthetic" } };
      else if (path === "/api/review/select-audio") result = handlers.selectAudio ? await handlers.selectAudio()
        : { cancelled: false, audio: initial.audio };
      else if (path === "/api/review/prepare-audio") result = { audio: { ...initial.audio, kind: "preview" } };
      else result = { closed: true, ok: true };
      return result as ReviewEndpoints[K];
    },
  };
  return { ...useReview(api, (key, values) => translate("zh-CN", key, values)), calls, handlers, presence };
}

test("人工回听默认关闭，明确开启后配置与返回编辑保留开关", async () => {
  const page = harness();
  await addAudio(page);
  assert.equal(page.form.reviewEnabled, false);
  page.form.reviewEnabled = true;
  await page.actions.validate();
  assert.equal(lastConfig(page).review_enabled, true);
  await page.actions.edit();
  assert.equal(page.form.reviewEnabled, true);
});

test("回听保存串行发送快照，等待中新增输入随后保存且不回写旧文本", async () => {
  const page = reviewHarness();
  await page.start();
  const pending = deferred<{ revision: number }>();
  let count = 0;
  page.handlers.save = async () => ++count === 1 ? pending.promise : { revision: 2 };
  page.changeSentence(1, { text: "第一批" });
  const saving = page.flush();
  page.changeSentence(1, { text: "第二批" });
  assert.equal(page.calls.filter(call => call.path.endsWith("/save")).length, 1);
  pending.resolve({ revision: 1 });
  assert.equal(await saving, true);
  const saves = page.calls.filter(call => call.path.endsWith("/save"));
  assert.deepEqual(saves.map(call => call.payload), [
    { revision: 0, sentences: [{ index: 1, text: "第一批", speaker_id: 0 }] },
    { revision: 1, sentences: [{ index: 1, text: "第二批", speaker_id: 0 }] },
  ]);
  assert.equal(page.document.value?.sentences[0].text, "第二批");
  assert.equal(page.dirtyCount.value, 0);
  page.dispose();
});

test("回听保存失败保留输入并暂停自动重试，明确重试才继续", async () => {
  const page = reviewHarness();
  await page.start();
  page.handlers.save = async () => { throw new Error("synthetic failure"); };
  page.changeSentence(1, { text: "失败后仍保留" });
  assert.equal(await page.flush(), false);
  page.changeSentence(2, { speaker_id: 0 });
  assert.equal(await page.flush(), false);
  assert.equal(page.calls.filter(call => call.path.endsWith("/save")).length, 1);
  assert.equal(page.document.value?.sentences[0].text, "失败后仍保留");
  assert.equal(page.dirtyCount.value, 2);
  page.handlers.save = async () => ({ revision: 1 });
  assert.equal(await page.retry(), true);
  assert.equal(page.dirtyCount.value, 0);
  page.dispose();
});

test("回听版本冲突保留修改且不允许重试覆盖或导出", async () => {
  const page = reviewHarness();
  await page.start();
  page.handlers.save = async () => { throw new ReviewRequestError({ zh: "冲突", en: "Conflict" }, 409); };
  page.changeSentence(1, { text: "本页输入" });
  await page.flush();
  assert.equal(page.conflict.value, true);
  assert.equal(page.editable.value, false);
  assert.equal(await page.retry(), false);
  await page.exportDocuments();
  assert.equal(page.calls.some(call => call.path.endsWith("/export")), false);
  assert.equal(page.document.value?.sentences[0].text, "本页输入");
  assert.equal(page.document.value?.revision, 0);
  page.dispose();
});

test("全局说话人名称与新增编号随句子归属同批保存", async () => {
  const page = reviewHarness();
  await page.start();
  page.renameSpeaker(0, "主持人");
  page.addSpeaker();
  page.renameSpeaker(1, "访谈对象");
  page.changeSentence(2, { speaker_id: 1 });
  await page.flush();
  assert.deepEqual(page.calls.at(-1)?.payload, { revision: 0,
    sentences: [{ index: 2, text: "第二句", speaker_id: 1 }], speakers: [{ id: 0, name: "主持人" }, { id: 1, name: "访谈对象" }] });
  page.renameSpeaker(0, "");
  await page.flush();
  assert.equal(page.document.value?.speakers[0].name, "");
  page.dispose();
});

test("导出前保存完成，导出后继续编辑标记旧成品过期，选择目录带独立编号", async () => {
  const page = reviewHarness();
  await page.start();
  page.changeSentence(1, { text: "导出前修改" });
  await page.exportDocuments();
  assert.deepEqual(page.calls.map(call => call.path), ["/api/review", "/api/review/save", "/api/review/export"]);
  assert.equal(page.document.value?.export_revision, 1);
  assert.equal(page.stale.value, false);
  assert.equal(page.editable.value, true);
  page.changeSentence(2, { text: "导出后修改" });
  assert.equal(page.stale.value, true);
  assert.equal(typeof (page.calls.at(-1)?.payload as { picker_id: string }).picker_id, "string");
  assert.equal(page.operation.value, null);
  page.dispose();
});

test("导出期间另页保存后，本页保持原文字版本且后续保存仍冲突", async () => {
  const page = reviewHarness();
  await page.start();
  const started = deferred<void>();
  const pending = deferred<ReviewEndpoints["/api/review/export"]>();
  page.handlers.export = async () => { started.resolve(); return pending.promise; };
  const exporting = page.exportDocuments();
  await started.promise;
  // 模拟另一页已保存新文字版本，旧页面的后续写入由服务端拒绝。
  page.handlers.save = async () => { throw new ReviewRequestError({ zh: "冲突", en: "Conflict" }, 409); };
  pending.resolve({ cancelled: false, export_revision: 0, delivery: { status: "COMPLETE", files: {}, message: "synthetic" } });
  await exporting;
  assert.equal(page.document.value?.revision, 0);
  assert.equal(page.document.value?.export_revision, 0);
  assert.equal(page.document.value?.speakers[0].name, "");
  assert.equal(page.stale.value, false);
  page.renameSpeaker(0, "本页输入");
  assert.equal(await page.flush(), false);
  assert.equal((page.calls.at(-1)?.payload as { revision: number }).revision, 0);
  assert.equal(page.document.value?.revision, 0);
  assert.equal(page.document.value?.speakers[0].name, "本页输入");
  assert.equal(page.conflict.value, true);
  page.dispose();
});

test("重选录音先保存编辑，再绑定音频且保持文字稿版本", async () => {
  const page = reviewHarness();
  await page.start();
  page.changeSentence(1, { text: "选择前修改" });
  assert.equal(await page.selectAudio(), true);
  assert.deepEqual(page.calls.slice(-2).map(call => call.path), ["/api/review/save", "/api/review/select-audio"]);
  assert.deepEqual(Object.keys(page.calls.at(-1)!.payload!), ["picker_id"]);
  assert.equal(page.document.value?.revision, 1);
  page.changeSentence(1, { text: "选择后修改" });
  await page.flush();
  assert.equal((page.calls.at(-1)?.payload as { revision: number }).revision, 1);
  page.dispose();
});

test("旧页重选录音保持原文字版本，之后修改姓名仍被版本冲突拒绝", async () => {
  const page = reviewHarness();
  await page.start();
  const before = JSON.stringify(page.document.value);
  assert.equal(await page.selectAudio(), true);
  assert.equal(page.document.value?.revision, 0);
  assert.equal(JSON.stringify(page.document.value), before);
  page.handlers.save = async () => { throw new ReviewRequestError({ zh: "冲突", en: "Conflict" }, 409); };
  page.renameSpeaker(0, "旧页面修改");
  assert.equal(await page.flush(), false);
  assert.equal((page.calls.at(-1)?.payload as { revision: number }).revision, 0);
  assert.equal(page.conflict.value, true);
  assert.equal(page.editable.value, false);
  assert.equal(page.operation.value, null);
  assert.equal(page.saveError.value?.describe("zh-CN"), translate("zh-CN", "reviewConflict"));
  await page.exportDocuments();
  assert.equal(await page.selectAudio(), false);
  assert.equal(await page.retry(), false);
  assert.equal(page.document.value?.speakers[0].name, "旧页面修改");
  assert.equal(page.document.value?.revision, 0);
  assert.equal(page.calls.length, 3);
  page.dispose();
});

test("重选录音不改变文字与导出版本，不使已导出稿过期", async () => {
  const page = reviewHarness();
  await page.start();
  page.renameSpeaker(0, "主持人");
  await page.exportDocuments();
  const before = JSON.stringify(page.document.value);
  assert.equal(await page.selectAudio(), true);
  assert.equal(JSON.stringify(page.document.value), before);
  assert.equal(page.document.value?.revision, 1);
  assert.equal(page.document.value?.export_revision, 1);
  assert.equal(page.stale.value, false);
  page.dispose();
});

test("取消重选录音保留版本和音频，页面仍可编辑", async () => {
  const page = reviewHarness();
  await page.start();
  const before = JSON.stringify(page.document.value);
  page.handlers.selectAudio = async () => ({ cancelled: true });
  assert.equal(await page.selectAudio(), false);
  assert.equal(JSON.stringify(page.document.value), before);
  assert.equal(page.conflict.value, false);
  assert.equal(page.editable.value, true);
  assert.equal(page.operation.value, null);
  page.dispose();
});


test("逐句重置恢复原始正文和归属，全局姓名保持修改", async () => {
  const page = reviewHarness();
  await page.start();
  const sentence = page.document.value!.sentences[0];
  page.renameSpeaker(0, "主持人");
  assert.equal(sentenceModified(sentence), false);
  page.changeSentence(1, { text: "新正文", speaker_id: null });
  assert.equal(sentenceModified(sentence), true);
  await page.flush();
  page.resetSentence(1);
  assert.equal(sentenceModified(sentence), false);
  assert.equal(page.document.value!.speakers[0].name, "主持人");
  await page.flush();
  assert.deepEqual(page.calls.at(-1)?.payload, { revision: 1, sentences: [{ index: 1, text: "原句", speaker_id: 0 }] });
  page.dispose();
});

test("取消目录选择保留已保存草稿和上次导出状态", async () => {
  const page = reviewHarness();
  await page.start();
  await page.exportDocuments();
  const delivery = page.document.value!.delivery;
  page.handlers.cancelled = true;
  page.changeSentence(1, { text: "取消前保存" });
  await page.exportDocuments();
  assert.equal(page.document.value!.revision, 1);
  assert.equal(page.document.value!.delivery, delivery);
  assert.equal(page.document.value!.export_revision, 0);
  assert.equal(page.stale.value, true);
  assert.equal(page.operation.value, null);
  assert.equal(page.editable.value, true);
  page.dispose();
});

test("离页仅关闭在场连接，缓存恢复不重读或覆盖未保存稿件", async () => {
  const page = reviewHarness();
  await page.start();
  page.changeSentence(1, { text: "缓存保留" });
  page.suspendPresence();
  assert.equal(page.presence.closed, 1);
  assert.equal(page.calls.length, 1);
  page.resumePresence();
  assert.equal(page.presence.opened, 2);
  assert.equal(page.document.value!.sentences[0].text, "缓存保留");
  assert.equal(page.calls.length, 1);
  page.dispose();
  assert.equal(page.presence.closed, 2);
});

test("在场连接使用同源SSE，关闭后解除回调且不发送关闭请求", () => {
  const source = { onopen: null as (() => void) | null, onerror: null as (() => void) | null, closed: false,
    // 记录连接关闭。
    close() { this.closed = true; } };
  let opened = 0, disconnected = 0;
  const api = createReviewApi(fetch, () => "en", (key, values) => translate("en", key, values), url => {
    assert.equal(url, "/api/review/presence"); return source as unknown as EventSource;
  });
  const stop = api.presence(() => { opened += 1; }, () => { disconnected += 1; });
  source.onopen!(); source.onerror!();
  assert.equal(opened, 1); assert.equal(disconnected, 1);
  stop();
  assert.equal(source.closed, true);
  assert.equal(source.onerror, null);
});
