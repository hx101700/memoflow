import { UiError } from "./api";
import type { Translate } from "./i18n";
import type { Configuration, FormValues, HotwordRow, Limits, Model, SessionEnd, ValidationResult } from "./types";

// 初始化页面阶段、音频选择、词表导入与凭据状态。
export function createModel(): Model {
  return {
    phase: "loading", revision: 0, preview: null, receipt: null, session: null,
    directories: { json: "default", document: "default" },
    audio: null, hotwordImport: { status: "empty", name: "", size: 0 },
    hotwords: { issues: [], warnings: [] },
    auth: { revision: 0, status: "idle" }, picker: null, downloadingTemplate: false, statusMessage: "",
  };
}

// 从同一份页面状态推导事件与控件的操作权限。
export function availability(model: Model) {
  const editable = ["editing", "validating"].includes(model.phase);
  const importing = model.hotwordImport.status === "importing";
  const pending = importing || model.auth.status === "loading" || model.auth.status === "saving" || Boolean(model.picker);
  return {
    editable,
    validate: editable && model.phase !== "validating" && !pending,
    edit: model.phase === "preview" && Boolean(model.preview),
    copy: model.phase === "preview" && Boolean(model.preview?.ready),
    selectAudio: editable && !model.picker,
    chooseDirectory: editable && !model.picker,
    cancelPicker: Boolean(model.picker) && !model.picker?.cancelling,
    template: editable && !model.downloadingTemplate,
    editHotwords: editable && !importing,
    changeAuth: editable && model.auth.status !== "saving",
    changeLanguage: !pending && !model.downloadingTemplate && !["validating", "returning"].includes(model.phase),
    importHotwords: editable && !importing,
  };
}

// 输入变化后作废旧预览，使迟到的校验结果失效。
export function invalidatePreview(model: Model): void {
  if (!availability(model).editable) return;
  model.revision += 1;
  model.preview = null;
  model.statusMessage = "";
  if (model.phase !== "validating") model.phase = "editing";
}

// 按输入版本接收校验结果并保存确认所需的预览。
export function receiveValidation(model: Model, revision: number, result: ValidationResult, config: Configuration): boolean {
  if (revision !== model.revision || model.phase !== "validating") return false;
  model.preview = { id: result.validation_id, summary: result.summary, configuration: config, ready: false };
  model.phase = "preview";
  return true;
}

// 接收会话结束结果并使未完成的输入请求失效。
export function receiveEnd(model: Model, result: SessionEnd): void {
  model.phase = result.state;
  model.preview = null;
  model.receipt = result.receipt;
  model.revision += 1;
  model.statusMessage = "";
  model.auth.revision += 1;
  model.auth.status = "idle";
}

// 按当前表格顺序生成传输行，保留错误原值并去除组件标识。
export function hotwordRows(form: FormValues): HotwordRow[] {
  return form.hotwordRows.map(entry => ({ text: entry.text, weight: entry.weight,
    ...(entry.invalid_fields ? { invalid_fields: [...entry.invalid_fields] } : {}) }));
}

// 根据普通表单与已选择音频构建确认配置。
export function configuration(model: Model, form: FormValues, limits: Limits, t: Translate): Configuration {
  let speakerCount: number | null = null;
  if (form.diarizationEnabled && form.speaker !== "") {
    speakerCount = Number(form.speaker);
    if (!Number.isInteger(speakerCount) || speakerCount < limits.speaker_min || speakerCount > limits.speaker_max) {
      throw new UiError(t("invalidSpeaker", { min: limits.speaker_min, max: limits.speaker_max }), "speaker_count");
    }
  }
  return {
    auth_mode: form.useApiKey ? "api_key" : "console",
    audio_id: model.audio?.audio_id ?? null, diarization_enabled: form.diarizationEnabled,
    enhancement_mode: form.hotwordsEnabled ? (form.contextEnabled ? "both" : "hotwords") : (form.contextEnabled ? "context" : "none"),
    hotword_rows: form.hotwordsEnabled ? hotwordRows(form) : [],
    context: form.contextEnabled ? form.context : "", language_hint: form.language || null,
    speaker_count: speakerCount, json_directory: model.directories.json, document_directory: model.directories.document,
  };
}

// 检查音频选择状态并指出选择区域。
export function checkRequiredInputs(config: Configuration, t: Translate): void {
  if (!config.audio_id) throw new UiError(t("missingAudio"), "audio_id");
}
