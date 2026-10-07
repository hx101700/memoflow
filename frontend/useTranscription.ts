import { nextTick, reactive, shallowRef } from "vue";
import { UiError, uiError } from "./api";
import { availability, checkRequiredInputs, configuration, createModel, receiveEnd, receiveValidation } from "./model";
import type { Translate } from "./i18n";
import type { Api, DirectoryKind, EditableSnapshot, FormValues, HotwordField, HotwordRow, SessionEnd } from "./types";

export interface ViewEffects {
  focus(target: string): void;
  setApiKey(value: string): void;
  getApiKey(): string;
  download(blob: Blob): void;
}

// 编排本机表单、只读预览和编辑会话结束，浏览器操作由视图提供。
export function useTranscription(api: Api, view: ViewEffects, t: Translate, makeRequestId: () => string = () => crypto.randomUUID()) {
  const model = reactive(createModel());
  const form = reactive<FormValues>({ useApiKey: false, diarizationEnabled: true, hotwordsEnabled: false,
    contextEnabled: false, context: "", language: "", speaker: "", hotwordRows: [] });
  const error = shallowRef<UiError | null>(null);
  let rowKey = 0;
  let stopListening: (() => void) | undefined;

  // 判断编辑会话是否仍允许接收本机操作结果。
  function active(): boolean { return !["handed_off", "expired", "cancelled", "unavailable"].includes(model.phase); }

  // 保存可见错误，并按用户当前操作定位输入。
  function fail(reason: unknown, field?: string): void {
    if (!active()) return;
    error.value = uiError(reason, () => t("failed"), field);
    if (error.value.field === "hotword_rows" && error.value.details.length) {
      model.hotwords.issues = error.value.details.map(issue => ({ ...issue,
        key: issue.row === undefined ? undefined : form.hotwordRows[issue.row - 1]?.key,
      }));
    }
    view.focus(error.value.field ?? "error-panel");
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
  }

  // 将后端保留的预览输入恢复到本机表单。
  function restoreForm(result: EditableSnapshot): void {
    const config = result.configuration;
    Object.assign(form, { useApiKey: config.auth_mode === "api_key", diarizationEnabled: config.diarization_enabled,
      hotwordsEnabled: ["hotwords", "both"].includes(config.enhancement_mode),
      contextEnabled: ["context", "both"].includes(config.enhancement_mode), context: config.context,
      language: config.language_hint ?? "", speaker: config.speaker_count === null ? "" : String(config.speaker_count) });
    setRows(config.hotword_rows);
    model.audio = { ...result.audio };
    model.directories = { json: config.json_directory, document: config.document_directory };
    Object.assign(model.hotwords, { issues: [], warnings: [] });
  }

  // 读取当前凭据方式，在视图中显示 API Key 并丢弃迟到结果。
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

  // 保存显示组件中的 API Key，并按凭据版本更新保存状态。
  async function persistApiKey(): Promise<boolean> {
    const revision = model.auth.revision;
    const value = view.getApiKey();
    if (!value) throw new UiError(() => t("keyNotReady"), "auth_mode");
    model.auth.status = "saving";
    try { await api.request("/api/save-api-key", { value }); }
    catch (reason) {
      if (revision === model.auth.revision) model.auth.status = "failed";
      throw uiError(reason, () => t("failed"), "auth_mode");
    }
    if (revision !== model.auth.revision || !active()) return false;
    model.auth.status = "ready";
    return true;
  }

  // 在预览渲染后登记版本，使 Codex 可以交接这份输入。
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
    model.preview = null;
    await nextTick();
    await updateAuth();
    if (model.auth.status !== "failed") view.focus("config-fields");
  }

  // 清除已改单元格的旧错误；重复组保留到只剩一个未改词条。
  function hotwordsChanged(key?: number, field?: HotwordField): void {
    if (key !== undefined) {
      const group = model.hotwords.issues.find(issue => issue.key === key && issue.duplicate_group !== undefined)?.duplicate_group;
      model.hotwords.issues = model.hotwords.issues.filter(issue =>
        !(issue.key === key && (!field || issue.field === field)));
      if ((!field || field === "text") && group !== undefined &&
          model.hotwords.issues.filter(issue => issue.duplicate_group === group).length < 2) {
        model.hotwords.issues = model.hotwords.issues.filter(issue => issue.duplicate_group !== group);
      }
    }
    if (error.value?.field === "hotword_rows" && !model.hotwords.issues.length) error.value = null;
  }

  // 清除当前字段的旧错误，保留其余区域的检查结果。
  function clearError(field: string): void {
    if (error.value?.field === field) error.value = null;
  }

  const actions = {
    // 标记凭据输入已修改，清除对应提示。
    keyChanged(): void {
      if (!availability(model).changeAuth) return;
      model.auth.revision += 1;
      model.auth.status = "dirty";
      clearError("auth_mode");
    },

    // 将当前 API Key 单独保存到工作目录并返回保存结果。
    async saveApiKey(): Promise<boolean> {
      if (!form.useApiKey || !availability(model).changeAuth || !["dirty", "failed"].includes(model.auth.status)) return false;
      clearError("auth_mode");
      try { return await persistApiKey(); }
      catch (reason) { fail(reason); return false; }
    },

    // 加载编辑会话、恢复已有预览并订阅一次性结束结果。
    async start(): Promise<void> {
      try {
        model.session = await api.request("/api/session");
        if (model.session.terminal) { ended(model.session.terminal); return; }
        stopListening = api.listen(ended, () => {
          if (!active()) return;
          error.value = new UiError(() => t("network"));
          model.phase = "unavailable";
          view.setApiKey("");
        });
        const preview = model.session.preview;
        if (preview) {
          restoreForm(preview);
          model.preview = { id: preview.validation_id, configuration: preview.configuration, summary: preview.summary, ready: false };
          model.phase = "preview";
          await registerPreview();
        } else {
          model.phase = "editing";
          model.audio = model.session.audio ? { ...model.session.audio } : null;
          if (model.session.audio_error) fail(new UiError(model.session.audio_error, "audio_id"));
        }
      } catch (reason) {
        error.value = uiError(reason, () => t("unavailableHelp"));
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
      clearError("auth_mode");
      await updateAuth();
    },

    // 输入改变时清除对应字段的错误说明。
    changed(field?: string): void {
      if (!availability(model).editable) return;
      if (field) clearError(field);
    },

    // 关闭热词增强时清空表格、导入信息和对应提示。
    setHotwordsEnabled(enabled: boolean): void {
      if (!availability(model).editHotwords) return;
      form.hotwordsEnabled = enabled;
      if (!enabled) {
        form.hotwordRows = [];
        model.hotwordImport = { status: "empty", name: "" };
        model.hotwords = { issues: [], warnings: [] };
      } else if (!form.hotwordRows.length) actions.addHotword();
      actions.changed("hotword_rows");
    },

    // 关闭上下文增强时清空参考文本和对应提示。
    setContextEnabled(enabled: boolean): void {
      if (!availability(model).editable) return;
      form.contextEnabled = enabled;
      if (!enabled) form.context = "";
      actions.changed("context");
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
      hotwordsChanged(key, field);
    },

    // 在热词表末尾添加独立标识的可编辑词条。
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
      hotwordsChanged(key);
    },

    // 读取单份 Excel 的字节，取得可编辑热词数组。
    async importHotwords(files: readonly File[]): Promise<void> {
      const session = model.session;
      if (!session || !availability(model).importHotwords || !files.length) return;
      model.hotwordImport = { status: "empty", name: "" };
      const imported = model.hotwordImport;
      try {
        if (files.length !== 1) throw new UiError(() => t("singleFile"), "hotword_rows");
        const file = files[0];
        if (!file.name.toLowerCase().endsWith(".xlsx")) throw new UiError(() => t("wrongHotwords"), "hotword_rows");
        if (file.size > session.limits.hotwords_bytes) throw new UiError(() => t("tooLarge", { size: session.limits.hotwords_bytes / 1_000_000 }), "hotword_rows");
        imported.status = "importing";
        imported.name = file.name;
        const result = await api.request("/api/import-hotwords", undefined, file);
        if (!active()) return;
        setRows(result.rows);
        clearError("hotword_rows");
        Object.assign(model.hotwords, { issues: [], warnings: result.warnings });
        Object.assign(imported, { status: "ready", name: result.name });
        view.focus("hotword_rows");
      } catch (reason) { imported.status = "failed"; fail(reason, "hotword_rows"); }
    },

    // 打开系统文件窗口并记录服务端登记的原录音引用。
    async selectAudio(): Promise<void> {
      if (!model.session || !availability(model).selectAudio) return;
      const id = makeRequestId();
      model.picker = { id, kind: "audio", cancelling: false };
      let failure: unknown;
      try {
        const result = await api.request("/api/select-audio", { picker_id: id });
        if (model.picker?.id !== id || !active()) return;
        if (!result.cancelled) {
          model.audio = { audio_id: result.audio_id, name: result.name, path: result.path, size_bytes: result.size_bytes };
          clearError("audio_id");
        }
      } catch (reason) { failure = reason; }
      finally { if (model.picker?.id === id) model.picker = null; }
      if (failure) fail(failure, "audio_id");
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
          clearError(`${kind}_directory`);
        }
      } catch (reason) { failure = reason; }
      finally { if (model.picker?.id === id) model.picker = null; }
      if (failure) fail(failure, `${kind}_directory`);
    },

    // 取消当前系统选择窗口，等待原请求结束后恢复按钮。
    async cancelPicker(): Promise<void> {
      const picker = model.picker;
      if (!picker || !availability(model).cancelPicker) return;
      picker.cancelling = true;
      try { await api.request("/api/cancel-picker", { picker_id: picker.id }); }
      catch (reason) {
        if (model.picker?.id === picker.id) { picker.cancelling = false; fail(reason); }
      }
    },

    // 恢复指定输出目录的默认位置。
    resetDirectory(kind: DirectoryKind): void {
      if (!availability(model).chooseDirectory) return;
      model.directories[kind] = "default";
      clearError(`${kind}_directory`);
    },

    // 后端撤销当前预览后恢复填写，并按需重新读取已保存 API Key。
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
        model.phase = "preview";
        fail(reason);
      }
    },

    // 检查本次输入，在独立预览完成渲染后登记可交接版本。
    async validate(): Promise<void> {
      const session = model.session;
      if (!session || !availability(model).validate) return;
      error.value = null;
      let config;
      try {
        config = configuration(model, form, session.limits, t);
        checkRequiredInputs(config, t);
      } catch (reason) { fail(reason); return; }
      model.phase = "validating";
      if (form.useApiKey && model.auth.status !== "ready") {
        try {
          const saved = await persistApiKey();
          if (!active()) return;
          if (!saved) return;
        } catch (reason) {
          if (!active()) return;
          model.phase = "editing";
          fail(reason);
          return;
        }
      }
      try {
        // 新一轮检查替换旧诊断，保留表格数据、行键和导入记录。
        model.hotwords.issues = [];
        const result = await api.request("/api/validate", config);
        if (!active()) return;
        receiveValidation(model, result, config);
        Object.assign(model.hotwords, { issues: [], warnings: [] });
        await registerPreview();
      } catch (reason) {
        if (!active()) return;
        if (!model.preview) model.phase = "editing";
        fail(reason);
      }
    },

    // 下载热词模板，保留其它表单操作。
    async downloadTemplate(): Promise<void> {
      if (!availability(model).template) return;
      model.downloadingTemplate = true;
      try { view.download(await api.template()); }
      catch (reason) { fail(reason); }
      finally { model.downloadingTemplate = false; }
    },
  };
  return { model, form, error, actions };
}
