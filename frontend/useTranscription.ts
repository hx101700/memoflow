import { nextTick, reactive, shallowRef } from "vue";
import { UiError, uiError } from "./api";
import { availability, checkRequiredInputs, configuration, createModel, hotwordRows, invalidatePreview, receiveEnd, receiveValidation } from "./model";
import type { Translate } from "./i18n";
import type { Api, DirectoryKind, EditableSnapshot, FormValues, HotwordField, HotwordRow, SessionEnd, UploadKind } from "./types";

export interface ViewEffects {
  focus(target: string): void;
  setApiKey(value: string): void;
  getApiKey(): string;
  download(blob: Blob): void;
}

// 编排本机表单、只读预览和会话结束，浏览器操作由视图提供。
export function useTranscription(api: Api, view: ViewEffects, t: Translate, makeRequestId: () => string = () => crypto.randomUUID()) {
  const model = reactive(createModel());
  const form = reactive<FormValues>({ useApiKey: false, diarizationEnabled: true, hotwordsEnabled: false,
    contextEnabled: false, context: "", language: "", speaker: "", hotwordRows: [] });
  const error = shallowRef<UiError | null>(null);
  let rowKey = 0;
  let checkingRevision: number | null = null;
  let stopListening: (() => void) | undefined;

  // 判断会话是否仍允许接收本机操作结果。
  function active(): boolean { return !["handed_off", "expired", "cancelled", "unavailable"].includes(model.phase); }

  // 保存可见错误，并按用户当前操作定位输入。
  function fail(reason: unknown, field?: string, focus = true): void {
    if (!active()) return;
    error.value = uiError(reason, t("failed"), field);
    if (error.value.field === "hotword_rows") model.hotwords.issues = error.value.details;
    if (focus) view.focus(error.value.field ?? "error-panel");
  }

  // 接收终态、清除显示凭据并停止结束通知。
  function ended(result: SessionEnd): void {
    stopListening?.();
    receiveEnd(model, result);
    error.value = null;
    view.setApiKey("");
    view.focus("session-ended");
  }

  // 为导入或恢复的数据分配稳定组件标识和当前序号。
  function setRows(rows: HotwordRow[]): void {
    form.hotwordRows = rows.map((row, index) => ({ ...row, row: index + 1, key: ++rowKey }));
    model.hotwords.revision += 1;
    model.hotwords.validatedRevision = model.hotwords.revision;
  }

  // 将后端保留的预览输入恢复到本机表单。
  function restoreForm(result: EditableSnapshot): void {
    const config = result.configuration;
    Object.assign(form, { useApiKey: config.auth_mode === "api_key", diarizationEnabled: config.diarization_enabled,
      hotwordsEnabled: ["hotwords", "both"].includes(config.enhancement_mode),
      contextEnabled: ["context", "both"].includes(config.enhancement_mode), context: config.context,
      language: config.language_hint ?? "", speaker: config.speaker_count === null ? "" : String(config.speaker_count) });
    setRows(config.hotword_rows);
    model.uploads.audio = { status: "ready", id: result.audio.upload_id, name: result.audio.name, size: result.audio.size_bytes };
    model.directories = { json: config.json_directory, document: config.document_directory };
    Object.assign(model.hotwords, { issues: [], warnings: [] });
  }

  // 读取当前凭据方式，在视图中显示 Key 并丢弃迟到结果。
  async function updateAuth(): Promise<void> {
    const revision = ++model.auth.revision;
    view.setApiKey("");
    if (!form.useApiKey) { model.auth.status = "idle"; return; }
    model.auth.status = "loading";
    try {
      const result = await api.request("/api/api-key", {});
      if (revision !== model.auth.revision || !active()) return;
      view.setApiKey(result.value);
      model.auth.status = result.value ? "ready" : "dirty";
    } catch (reason) {
      if (revision !== model.auth.revision || !active()) return;
      model.auth.status = "failed";
      fail(reason, "auth_mode");
    }
  }

  // 保存显示组件中的 Key，并按凭据版本更新保存状态。
  async function persistApiKey(): Promise<boolean> {
    const revision = model.auth.revision;
    const value = view.getApiKey();
    if (!value) throw new UiError(t("keyNotReady"), "auth_mode");
    model.auth.status = "saving";
    try { await api.request("/api/save-api-key", { value }); }
    catch (reason) {
      if (revision === model.auth.revision) model.auth.status = "failed";
      throw uiError(reason, t("failed"), "auth_mode");
    }
    if (revision !== model.auth.revision || !active()) return false;
    model.auth.status = "ready";
    return true;
  }

  // 在预览渲染后登记版本，使代码入口可以接管这份输入。
  async function registerPreview(): Promise<void> {
    const preview = model.preview;
    if (!preview) return;
    await nextTick();
    if (model.phase !== "preview" || model.preview?.id !== preview.id) return;
    try { await api.request("/api/preview-ready", { validation_id: preview.id }); }
    catch (reason) {
      if (model.phase === "preview" && model.preview?.id === preview.id) throw reason;
      return;
    }
    if (model.phase !== "preview" || model.preview?.id !== preview.id) return;
    preview.ready = true;
    view.setApiKey("");
    view.focus("review");
  }

  // 恢复已撤销预览的编辑权限，并读取当前凭据。
  async function resumeEditing(): Promise<void> {
    model.phase = "editing";
    invalidatePreview(model);
    await nextTick();
    await updateAuth();
    if (model.auth.status !== "failed") view.focus("config-fields");
  }

  // 标记词表内容变化，使旧结果过期并等待离开整个区域后检查。
  function hotwordsChanged(): void {
    model.hotwords.revision += 1;
    model.hotwords.issues = [];
    model.hotwords.warnings = [];
    actions.changed();
  }

  const actions = {
    // 标记凭据输入已修改，使当前预览失效。
    keyChanged(): void {
      if (!availability(model).changeAuth) return;
      model.auth.revision += 1;
      model.auth.status = "dirty";
      error.value = null;
      invalidatePreview(model);
    },

    // 将当前 Key 单独保存到工作目录并返回保存结果。
    async saveApiKey(): Promise<boolean> {
      if (!form.useApiKey || !availability(model).changeAuth || !["dirty", "failed"].includes(model.auth.status)) return false;
      error.value = null;
      try { return await persistApiKey(); }
      catch (reason) { fail(reason); return false; }
    },

    // 加载会话、恢复已有预览并订阅一次性结束结果。
    async start(): Promise<void> {
      try {
        model.session = await api.request("/api/session");
        if (model.session.terminal) { ended(model.session.terminal); return; }
        stopListening = api.listen(ended, () => {
          if (!active()) return;
          error.value = new UiError(t("network"));
          model.phase = "unavailable";
          view.setApiKey("");
        });
        const preview = model.session.preview;
        if (preview) {
          restoreForm(preview);
          model.preview = { id: preview.validation_id, configuration: preview.configuration, summary: preview.summary, ready: false };
          model.phase = "preview";
          await registerPreview();
        } else model.phase = "editing";
      } catch (reason) {
        error.value = uiError(reason, t("failed"));
        model.phase = "unavailable";
        stopListening?.();
      }
    },

    // 页面卸载时释放结束通知连接。
    dispose(): void { stopListening?.(); },

    // 切换认证方式并读取或清空密码输入框。
    async setAuthMode(useApiKey: boolean): Promise<void> {
      if (!availability(model).changeAuth) return;
      form.useApiKey = useApiKey;
      error.value = null;
      invalidatePreview(model);
      await updateAuth();
    },

    // 输入改变时作废旧预览及对应的错误说明。
    changed(): void {
      if (!availability(model).editable) return;
      error.value = null;
      invalidatePreview(model);
    },

    // 按组件标识更新单元格并清除该格的导入类型标记。
    changeHotword(key: number, field: HotwordField, value: string): void {
      if (!availability(model).editHotwords) return;
      const row = form.hotwordRows.find(entry => entry.key === key);
      if (!row || row[field] === value) return;
      row[field] = value;
      if (row.invalid_fields) {
        row.invalid_fields = row.invalid_fields.filter(invalid => invalid !== field);
        if (!row.invalid_fields.length) delete row.invalid_fields;
      }
      hotwordsChanged();
    },

    // 在词表末尾添加独立标识的可编辑词条。
    addHotword(): void {
      if (!availability(model).editHotwords) return;
      form.hotwordRows.push({ key: ++rowKey, row: form.hotwordRows.length + 1, text: "", weight: 4 });
      hotwordsChanged();
    },

    // 删除词条后按当前位置重排显示序号。
    removeHotword(key: number): void {
      if (!availability(model).editHotwords) return;
      form.hotwordRows = form.hotwordRows.filter(entry => entry.key !== key);
      form.hotwordRows.forEach((row, index) => { row.row = index + 1; });
      hotwordsChanged();
    },

    // 区域失焦后检查已修改的词表，迟到结果按词表版本丢弃。
    async checkHotwords(): Promise<void> {
      if (model.phase !== "editing" || !availability(model).editHotwords) return;
      const revision = model.hotwords.revision;
      if (revision === model.hotwords.validatedRevision || revision === checkingRevision) return;
      checkingRevision = revision;
      model.hotwords.checking = true;
      try {
        const result = await api.request("/api/validate-hotwords", { rows: hotwordRows(form) });
        if (revision !== model.hotwords.revision || model.phase !== "editing") return;
        Object.assign(model.hotwords, { issues: result.issues, warnings: result.warnings, validatedRevision: revision });
      } catch (reason) {
        if (revision === model.hotwords.revision && model.phase === "editing") fail(reason, "hotword_rows", false);
      } finally {
        if (checkingRevision === revision) { checkingRevision = null; model.hotwords.checking = false; }
      }
    },

    // 切换界面语言时清除编辑区旧语言的检查提示。
    languageChanged(): void {
      if (!availability(model).changeLanguage || !availability(model).editable) return;
      error.value = null;
      model.hotwords.issues = [];
      model.hotwords.warnings = [];
      model.hotwords.validatedRevision = -1;
    },

    // 将单个文件传入本机服务，保存音频引用或可编辑热词数组。
    async upload(kind: UploadKind, files: readonly File[]): Promise<void> {
      const session = model.session;
      if (!session || !availability(model).upload[kind] || !files.length) return;
      error.value = null;
      invalidatePreview(model);
      model.uploads[kind] = { status: "empty", id: null, name: "", size: 0 };
      const upload = model.uploads[kind];
      const field = kind === "audio" ? "audio_upload_id" : "hotword_rows";
      try {
        if (files.length !== 1) throw new UiError(t("singleFile"), field);
        const file = files[0];
        const suffixes = kind === "audio" ? session.audio_suffixes : [".xlsx"];
        if (!suffixes.some(extension => file.name.toLowerCase().endsWith(extension))) {
          throw new UiError(t(kind === "hotwords" ? "wrongHotwords" : "unsupportedFormat"), field);
        }
        const limit = session.limits[kind === "audio" ? "audio_bytes" : "hotwords_bytes"];
        if (file.size > limit) throw new UiError(t("tooLarge", { size: limit / 1_000_000 }), field);
        upload.status = "uploading";
        upload.name = file.name;
        if (kind === "audio") {
          const result = await api.request("/api/upload-audio", undefined, file);
          if (!active()) return;
          Object.assign(upload, { status: "ready", id: result.upload_id, name: result.name, size: result.size_bytes });
        } else {
          const result = await api.request("/api/upload-hotwords", undefined, file);
          if (!active()) return;
          setRows(result.rows);
          Object.assign(model.hotwords, { issues: result.issues, warnings: result.warnings });
          Object.assign(upload, { status: "ready", name: result.name, size: result.size_bytes });
          view.focus("hotword_rows");
        }
      } catch (reason) { upload.status = "failed"; fail(reason, field); }
    },

    // 等待系统目录选择结果，选定后更新已批准的保存位置。
    async selectDirectory(kind: DirectoryKind): Promise<void> {
      if (!availability(model).chooseDirectory) return;
      const id = makeRequestId();
      model.picker = { id, kind, cancelling: false };
      let failure: unknown;
      try {
        const result = await api.request("/api/select-directory", { kind, picker_id: id });
        if (model.picker?.id !== id || !active()) return;
        if (!result.cancelled) {
          model.directories[kind] = result.path;
          error.value = null;
          invalidatePreview(model);
        }
      } catch (reason) { failure = reason; }
      finally { if (model.picker?.id === id) model.picker = null; }
      if (failure) fail(failure, `${kind}_directory`);
    },

    // 取消当前目录选择，等待原请求结束后恢复按钮。
    async cancelDirectory(): Promise<void> {
      const picker = model.picker;
      if (!picker || !availability(model).cancelDirectory) return;
      picker.cancelling = true;
      try { await api.request("/api/cancel-directory", { picker_id: picker.id }); }
      catch (reason) {
        if (model.picker?.id === picker.id) { picker.cancelling = false; fail(reason); }
      }
    },

    // 恢复指定输出目录的默认位置。
    resetDirectory(kind: DirectoryKind): void {
      if (!availability(model).chooseDirectory) return;
      model.directories[kind] = "default";
      error.value = null;
      invalidatePreview(model);
    },

    // 后端撤销当前预览后恢复填写，并按需重新读取已保存 Key。
    async edit(): Promise<void> {
      if (!availability(model).edit || !model.preview) return;
      const validationId = model.preview.id;
      model.preview.ready = false;
      model.phase = "returning";
      error.value = null;
      try {
        const result = await api.request("/api/edit", { validation_id: validationId });
        if (!active()) return;
        restoreForm(result);
        await resumeEditing();
      } catch (reason) {
        if (!active()) return;
        try {
          // 返回响应丢失时，仅核对一次服务端状态，恢复仍保留在本页的输入。
          const session = await api.request("/api/session");
          if (!active()) return;
          if (session.session_id === model.session?.session_id) {
            if (session.terminal) { ended(session.terminal); return; }
            if (session.phase === "editing" && !session.preview) { await resumeEditing(); return; }
          }
        } catch { /* 状态仍未知时保留只读预览，显示原操作错误。 */ }
        if (!active()) return;
        model.phase = "preview";
        fail(reason);
      }
    },

    // 检查本次输入，在独立预览完成渲染后登记可交接版本。
    async validate(): Promise<void> {
      const session = model.session;
      if (!session || !availability(model).validate) return;
      error.value = null;
      invalidatePreview(model);
      let config;
      try {
        config = configuration(model, form, session.limits, t);
        checkRequiredInputs(config, session.limits, t);
      } catch (reason) { fail(reason); return; }
      const revision = model.revision;
      model.phase = "validating";
      if (form.useApiKey && model.auth.status !== "ready") {
        try {
          const saved = await persistApiKey();
          if (!active()) return;
          if (!saved || revision !== model.revision) { model.phase = "editing"; return; }
        } catch (reason) {
          if (!active()) return;
          // Key保存期间凭据不可改动，其他表单变化不能使本次凭据错误过期。
          model.phase = "editing";
          fail(reason);
          return;
        }
      }
      try {
        const result = await api.request("/api/validate", config);
        if (!active()) return;
        if (!receiveValidation(model, revision, result, config)) {
          await api.request("/api/edit", { validation_id: result.validation_id });
          if (!active()) return;
          model.phase = "editing";
          model.statusMessage = "changed";
          return;
        }
        Object.assign(model.hotwords, { issues: [], warnings: [], validatedRevision: model.hotwords.revision });
        await registerPreview();
      } catch (reason) {
        if (!active()) return;
        if (!model.preview) model.phase = "editing";
        if (revision === model.revision) fail(reason);
      }
    },

    // 下载热词模板，保留其它表单操作。
    async downloadTemplate(): Promise<void> {
      if (!availability(model).template) return;
      model.downloadingTemplate = true;
      error.value = null;
      try { view.download(await api.template()); }
      catch (reason) { fail(reason); }
      finally { model.downloadingTemplate = false; }
    },
  };
  return { model, form, error, actions };
}
