import assert from "node:assert/strict";
import test from "node:test";
import { useTranscription, type ViewEffects } from "../frontend/useTranscription";
import { createApi, UiError } from "../frontend/api";
import { availability, configuration, createModel, hotwordRows } from "../frontend/model";
import { localize, translate, type Translate } from "../frontend/i18n";
import type { Api, Configuration, EditorIssue, Endpoints, ErrorDetail, Language, Limits, Receipt, SessionDescription, SessionEnd, ValidationResult } from "../frontend/types";

const limits: Limits = { hotwords_bytes: 5_000_000, upload_bytes: 1_000_000_000,
  audio_seconds: 43200, hotwords_count: 2000, context_chars: 400, speaker_min: 2, speaker_max: 100 };
const description: SessionDescription = { session_id: "session-one", phase: "editing", expires_at: "2026-10-04T12:00:00Z",
  model: "fixed-model", region: "cn-beijing", limits, audio_suffixes: [".wav"], languages: ["zh"],
  output_defaults: { json: "D:/example", document: "D:/example" }, preview: null, terminal: null };
const audio = { name: "sample.wav", size: 15, path: "D:/recordings/sample.wav" };
const words = new File(["synthetic spreadsheet"], "words.xlsx");
const receipt: Receipt = { session_id: "session-one", job_id: "job", config_path: "fixture/config.json", json_directory: "fixture/json",
  document_directory: "fixture/documents", auth_mode: "console", execution_started: false };

// 生成具备真实协议字段的合成预览。
function validation(id = "validation-1"): ValidationResult {
  return { validation_id: id, summary: { auth_mode: "console", audio: { name: audio.name, path: audio.path, duration_seconds: 2,
    size_bytes: audio.size, format_name: "wav", channels: 1, sample_rate: 16000 },
    enhancement: { mode: "none", count: 0, context_chars: 0 }, json_directory: "fixture/json",
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
    listen(ended, disconnected) {
      view.subscriptions += 1;
      endListener = ended;
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
  page.actions.dispose();
  assert.equal(page.view.closed, 1);
});

test("启动失败与事件断线显示不可用，禁止继续确认或修改", async () => {
  const failed = harness({ "/api/session": () => { throw new Error("服务不可用"); } });
  await failed.actions.start();
  assert.equal(failed.model.phase, "unavailable");
  assert.equal(failed.error.value?.describe("zh-CN"), failed.t("unavailableHelp"));
  const page = harness();
  await preview(page);
  page.disconnect();
  await page.actions.edit();
  assert.equal(page.model.phase, "unavailable");
  assert.equal(availability(page.model).copy, false);
  assert.equal(page.calls.some(call => call.path === "/api/edit"), false);
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
  ready.reject(new UiError(() => "预览已退出", undefined, 422));
  await checking;
  assert.equal(page.model.phase, "returning");
  assert.equal(page.error.value, null);
  editing.resolve({ ok: true, configuration: lastConfig(page), audio: { audio_id: "audio-1", name: audio.name, path: "D:/recordings/sample.wav", size_bytes: audio.size } });
  await returning;
  assert.equal(page.model.phase, "editing");
  assert.equal(page.error.value, null);
});

test("返回修改被拒绝保持只读预览，直到明确终态到达", async () => {
  const page = harness({ "/api/edit": () => { throw new UiError(() => "会话已交接", undefined, 409); } });
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

test("返回编辑已成功但响应丢失时只读取一次状态并恢复本页输入", async () => {
  const page = harness({ "/api/edit": () => { throw new Error("response lost"); } });
  await addAudio(page);
  page.form.contextEnabled = true;
  page.form.context = "保留原始输入";
  await page.actions.validate();
  await page.actions.edit();
  assert.equal(page.model.phase, "editing");
  assert.equal(page.model.preview, null);
  assert.equal(page.form.context, "保留原始输入");
  assert.equal(page.model.audio?.audio_id, "audio-1");
  assert.equal(page.calls.filter(call => call.path === "/api/session").length, 2);
  assert.equal(page.calls.filter(call => call.path === "/api/edit").length, 1);
  assert.equal(page.error.value, null);
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
  pending.reject(new UiError(() => "请修正热词。", "hotword_rows", 422,
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
  const config: Configuration = { auth_mode: "api_key", audio_id: "audio-kept", diarization_enabled: false,
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
  assert.equal(page.t("confirmationMessage", { id: "session-one" }), "Confirm transcription. Session ID: session-one");
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
    "/api/validate": () => { throw new UiError({ zh: "请修正热词。", en: "Correct the hotword list." }, "hotword_rows", 422, issues); } });
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
  page.handlers["/api/validate"] = () => { throw new UiError(() => "请添加热词。", "hotword_rows", 422); };
  await page.actions.validate();
  assert.equal(page.error.value?.field, "hotword_rows");
  page.form.hotwordsEnabled = false;
  page.form.contextEnabled = true;
  page.form.context = " \n\t";
  page.handlers["/api/validate"] = () => { throw new UiError(() => "内容仅包含空白，共3个字符。", "context", 422); };
  await page.actions.validate();
  assert.equal(page.form.context, " \n\t");
  assert.equal(page.view.focus, "context");
  assert.equal(page.error.value?.message, "内容仅包含空白，共3个字符。");
  assert.equal(lastConfig(page).context, " \n\t");
  assert.equal(page.calls.filter(call => call.path === "/api/validate").length, 2);
});

test("超长上下文原样发送后显示服务器错误，关闭发言人区分忽略旧人数", async () => {
  const page = harness({ "/api/session": () => ({ ...description, limits: { ...limits, speaker_max: 4, context_chars: 3 } }) });
  await addAudio(page);
  page.form.speaker = "1e";
  await page.actions.validate();
  assert.equal(page.error.value?.field, "speaker_count");
  page.form.diarizationEnabled = false;
  page.form.contextEnabled = true;
  page.form.context = "甲乙丙丁";
  page.handlers["/api/validate"] = () => { throw new UiError(() => "参考文本超出1个字符。", "context", 422); };
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
  pending.reject(new UiError(() => "Key含有空白，请修正。", "auth_mode", 422));
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
  const page = harness({ "/api/validate": () => { throw new UiError(() => "请修正热词。", "hotword_rows", 422, [detail]); },
    "/api/import-hotwords": () => { throw new UiError({ zh: "当前 Excel 未按模板导入。", en: "Use the Excel template." }, "hotword_rows", 422); } });
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
    "/api/validate": () => { throw new UiError(() => "请修改热词表。", "hotword_rows", 422, details); } });
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
    "/api/validate": () => { throw new UiError(() => "超级热词超过上限。", "hotword_rows", 422,
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
    throw new UiError({ zh: "上下文为空。", en: "Context is empty." }, "context", 422);
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
    "/api/validate": () => { throw new UiError(() => "请修改热词表。", "hotword_rows", 422,
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
      "/api/validate": () => { throw new UiError(() => "请修改热词表。", "hotword_rows", 422, details); } });
    await addAudio(page);
    page.actions.setHotwordsEnabled(true);
    await page.actions.importHotwords([words]);
    await page.actions.validate();
    const [first, second, third] = page.form.hotwordRows;
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
      "/api/validate": () => { throw new UiError(() => "请修改热词表。", "hotword_rows", 422, details); } });
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
    "/api/validate": () => { throw new UiError(() => "请修改热词表。", "hotword_rows", 422, details); } });
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
    "/api/validate": () => { throw new UiError({ zh: "上下文过长。", en: "Context is too long." }, "context", 422); } });
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
    (reason: unknown) => reason instanceof UiError && reason.httpStatus === 422 && reason.field === "context");
  assert.equal(sent?.credentials, "same-origin");
  assert.equal(new Headers(sent?.headers).get("Accept-Language"), "en");
  assert.equal(new Headers(sent?.headers).has("X-ASR-Token"), false);
  assert.equal(JSON.parse(sent?.body as string).context, "a\n'\\中文");
});

test("结束事件读取一次后关闭，连接失败也关闭且不自动重连", () => {
  let listener: EventListener = () => undefined;
  let closed = 0;
  let opened = 0;
  let ended: SessionEnd | null = null;
  let disconnected = 0;
  const source = { onerror: null as (() => void) | null,
    // 记录结束事件回调。
    addEventListener(name: string, callback: EventListener) { assert.equal(name, "ended"); listener = callback; },
    // 记录连接关闭。
    close() { closed += 1; } };
  const t: Translate = (key, values) => translate("en", key, values);
  const api = createApi(fetch, () => "en", t, url => { opened += 1; assert.equal(url, "/api/events"); return source as unknown as EventSource; });
  api.listen(result => { ended = result; }, () => { disconnected += 1; });
  listener(new MessageEvent("ended", { data: JSON.stringify({ state: "expired", receipt: null }) }));
  assert.deepEqual(ended, { state: "expired", receipt: null });
  assert.equal(closed, 1);
  source.onerror?.();
  assert.equal(disconnected, 1);
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
