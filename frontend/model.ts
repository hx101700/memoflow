import { UiError } from "./api";
import type { Translate } from "./i18n";
import type { Configuration, FormValues, HotwordRow, Limits, Model, SessionEnd, ValidationResult } from "./types";

// 初始化页面阶段、上传引用、凭据读取和目录选择状态。
export function createModel(): Model {
  return {
    phase: "loading", revision: 0, preview: null, receipt: null, session: null,
    directories: { json: "default", document: "default" },
    uploads: {
      audio: { status: "empty", id: null, name: "", size: 0 },
      hotwords: { status: "empty", id: null, name: "", size: 0 },
    },
    hotwords: { issues: [], warnings: [], checking: false, revision: 0, validatedRevision: 0 },
    auth: { revision: 0, status: "idle" }, picker: null, downloadingTemplate: false, statusMessage: "",
  };
}

// 从同一份页面状态推导事件与控件的操作权限。
export function availability(model: Model) {
  const editable = ["editing", "validating"].includes(model.phase);
  const uploading = Object.values(model.uploads).some(upload => upload.status === "uploading");
  const pending = uploading || model.auth.status === "loading" || model.auth.status === "saving" || Boolean(model.picker);
  return {
    editable,
    validate: editable && model.phase !== "validating" && !pending,
    edit: model.phase === "preview" && Boolean(model.preview),
    copy: model.phase === "preview" && Boolean(model.preview?.ready),
    chooseDirectory: editable && !model.picker,
    cancelDirectory: Boolean(model.picker) && !model.picker?.cancelling,
    template: editable && !model.downloadingTemplate,
    editHotwords: editable && model.uploads.hotwords.status !== "uploading",
    changeAuth: editable && model.auth.status !== "saving",
    changeLanguage: !pending && !model.downloadingTemplate && !["validating", "returning"].includes(model.phase),
    upload: {
      audio: editable && model.uploads.audio.status !== "uploading",
      hotwords: editable && model.uploads.hotwords.status !== "uploading",
    },
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
  model.hotwords.checking = false;
}

// 按当前表格顺序生成传输行，保留错误原值并去除组件标识。
export function hotwordRows(form: FormValues): HotwordRow[] {
  return form.hotwordRows.map(entry => ({ text: entry.text, weight: entry.weight,
    ...(entry.invalid_fields ? { invalid_fields: [...entry.invalid_fields] } : {}) }));
}

// 根据普通表单与上传引用构建确认配置。
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
    audio_upload_id: model.uploads.audio.id, diarization_enabled: form.diarizationEnabled,
    enhancement_mode: form.hotwordsEnabled ? (form.contextEnabled ? "both" : "hotwords") : (form.contextEnabled ? "context" : "none"),
    hotword_rows: form.hotwordsEnabled ? hotwordRows(form) : [],
    context: form.contextEnabled ? form.context : "", language_hint: form.language || null,
    speaker_count: speakerCount, json_directory: model.directories.json, document_directory: model.directories.document,
  };
}

// 检查必填输入并保留超长上下文的全部原文供用户修改。
export function checkRequiredInputs(config: Configuration, limits: Limits, t: Translate): void {
  if (!config.audio_upload_id) throw new UiError(t("missingAudio"), "audio_upload_id");
  if (["both", "hotwords"].includes(config.enhancement_mode) && !config.hotword_rows.length) {
    throw new UiError(t("missingHotwords"), "hotword_rows");
  }
  if (["both", "context"].includes(config.enhancement_mode)) {
    const length = Array.from(config.context).length;
    if (!config.context.trim()) throw new UiError(t("missingContext", { length, count: limits.context_chars }), "context");
    if (length > limits.context_chars) {
      throw new UiError(t("contextTooLong", { length, count: limits.context_chars, excess: length - limits.context_chars }), "context");
    }
  }
}
