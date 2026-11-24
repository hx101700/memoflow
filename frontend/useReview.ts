import { computed, ref, shallowRef } from "vue";
import { uiError, type UiError } from "./api";
import { ReviewRequestError } from "./review";
import type { Translate } from "./i18n";
import type { ReviewApi, ReviewDelivery, ReviewDocument } from "./types";

// 管理可编辑回听稿，串行保存局部修改并在导出前保存完毕。
export function useReview(api: ReviewApi, t: Translate) {
  const document = ref<ReviewDocument | null>(null);
  const error = shallowRef<UiError | null>(null);
  const saveError = shallowRef<UiError | null>(null);
  const conflict = ref(false);
  const connectionError = ref(false);
  const saving = ref(false);
  const operation = ref<"export" | "select" | "prepare" | null>(null);
  const dirtyCount = ref(0);
  const dirtySentences = new Map<number, number>();
  let speakerGeneration = 0;
  let generation = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let inFlight: Promise<boolean> | null = null;
  let disposed = false;
  let stopPresence: (() => void) | undefined;
  const editable = computed(() => Boolean(document.value && !document.value.closed && !operation.value && !conflict.value));

  // 记录待保存数量，失败后仅保留输入，等待用户明确重试。
  function schedule(): void {
    dirtyCount.value = dirtySentences.size + Number(speakerGeneration > 0);
    clearTimeout(timer);
    if (!saveError.value && !disposed) timer = setTimeout(() => { void flush(); }, 800);
  }

  // 保存一次捕获的修改；期间新增输入留在下一批中，不覆盖正在编辑的内容。
  async function saveLoop(): Promise<boolean> {
    const draft = document.value;
    if (!draft || draft.closed || saveError.value || disposed) return false;
    saving.value = true;
    try {
      while (dirtySentences.size || speakerGeneration) {
        const captured = new Map(dirtySentences);
        const capturedSpeakers = speakerGeneration;
        const sentences = draft.sentences.filter(row => captured.has(row.index))
          .map(({ index, text, speaker_id }) => ({ index, text, speaker_id }));
        const result = await api.request("/api/review/save", { revision: draft.revision,
          ...(sentences.length ? { sentences } : {}),
          ...(capturedSpeakers ? { speakers: draft.speakers.map(speaker => ({ ...speaker })) } : {}) });
        draft.revision = result.revision;
        for (const [index, version] of captured) if (dirtySentences.get(index) === version) dirtySentences.delete(index);
        if (speakerGeneration === capturedSpeakers) speakerGeneration = 0;
        dirtyCount.value = dirtySentences.size + Number(speakerGeneration > 0);
      }
      return true;
    } catch (reason) {
      conflict.value = reason instanceof ReviewRequestError && reason.status === 409;
      saveError.value = conflict.value ? uiError(null, () => t("reviewConflict")) : uiError(reason, () => t("reviewSaveFailed"));
      return false;
    } finally { saving.value = false; }
  }

  // 等待同一保存队列完成，失败时不自动重试。
  function flush(): Promise<boolean> {
    clearTimeout(timer);
    if (!inFlight) inFlight = saveLoop().finally(() => { inFlight = null; });
    return inFlight;
  }

  // 加载本机校对稿的已保存内容、版本与音频信息。
  async function start(): Promise<void> {
    try { document.value = await api.request("/api/review"); resumePresence(); }
    catch (reason) { error.value = uiError(reason, () => t("unavailableHelp")); }
  }

  // 恢复浏览器在场连接，bfcache返回时复用本页未保存输入。
  function resumePresence(): void {
    stopPresence?.();
    if (!document.value || document.value.closed || disposed) return;
    stopPresence = api.presence(() => { connectionError.value = false; }, () => { connectionError.value = true; });
    if (dirtyCount.value) schedule();
  }

  // 页面离开时释放在场连接，不额外发送保存或关闭请求。
  function suspendPresence(): void { stopPresence?.(); stopPresence = undefined; clearTimeout(timer); }

  // 更新单句正文或说话人归属，并安排自动保存。
  function changeSentence(index: number, change: { text?: string; speaker_id?: number | null }): void {
    if (!editable.value) return;
    const sentence = document.value?.sentences.find(row => row.index === index);
    if (!sentence) return;
    Object.assign(sentence, change);
    dirtySentences.set(index, ++generation);
    schedule();
  }

  // 恢复本句原文和原始归属，沿用正常保存流程且不改变全局姓名。
  function resetSentence(index: number): void {
    const sentence = document.value?.sentences.find(row => row.index === index);
    if (sentence) changeSentence(index, { text: sentence.original_text, speaker_id: sentence.original_speaker_id });
  }

  // 全局修改说话人名称，空名称恢复编号显示。
  function renameSpeaker(id: number, name: string): void {
    if (!editable.value) return;
    const speaker = document.value?.speakers.find(entry => entry.id === id);
    if (!speaker) return;
    speaker.name = name;
    speakerGeneration = ++generation;
    schedule();
  }

  // 新增当前稿件内唯一编号的说话人，供各句重新归属。
  function addSpeaker(): void {
    if (!editable.value || !document.value) return;
    const id = document.value.speakers.reduce((max, speaker) => Math.max(max, speaker.id), -1) + 1;
    document.value.speakers.push({ id, name: "" });
    speakerGeneration = ++generation;
    schedule();
  }

  // 用户明确重试后恢复保存队列；版本冲突必须先重新核对。
  async function retry(): Promise<boolean> {
    if (conflict.value) return false;
    saveError.value = null;
    return flush();
  }

  // 先保存全部编辑，再导出校验稿并返回本次结果。
  async function exportDocuments(): Promise<ReviewDelivery | null> {
    if (!editable.value || !document.value) return null;
    operation.value = "export";
    error.value = null;
    try {
      if (!await flush()) return null;
      const result = await api.request("/api/review/export", { revision: document.value.revision, picker_id: crypto.randomUUID() });
      if (result.cancelled) return null;
      if (result.delivery.status !== "COMPLETE") {
        const message = result.delivery.status === "PARTIAL" ? "reviewExportPartial" : "reviewExportFailed";
        error.value = uiError(null, () => t(message));
      }
      return result.delivery;
    } catch (reason) { operationFailed(reason); return null; }
    finally { operation.value = null; }
  }

  // 保留失败操作的双语提示，冲突时停止后续写入。
  function operationFailed(reason: unknown): void {
    if (reason instanceof ReviewRequestError && reason.status === 409) {
      conflict.value = true;
      error.value = uiError(null, () => t("reviewConflict"));
    } else error.value = uiError(reason, () => t("failed"));
  }

  // 保存草稿后重新绑定录音，保持本页的文字稿版本。
  async function selectAudio(): Promise<boolean> {
    if (!editable.value || !document.value) return false;
    operation.value = "select";
    error.value = null;
    try {
      if (!await flush()) return false;
      const result = await api.request("/api/review/select-audio", { picker_id: crypto.randomUUID() });
      if (result.cancelled) return false;
      document.value.audio = result.audio;
      return true;
    } catch (reason) { operationFailed(reason); return false; }
    finally { operation.value = null; }
  }

  // 请求后端生成或复用浏览器播放副本，不改变转写原稿。
  async function prepareAudio(): Promise<boolean> {
    if (!document.value || document.value.closed || operation.value) return false;
    operation.value = "prepare";
    try {
      const result = await api.request("/api/review/prepare-audio", {});
      document.value.audio = result.audio;
      return result.audio.available;
    } catch (reason) { error.value = uiError(reason, () => t("reviewAudioUnsupported")); return false; }
    finally { operation.value = null; }
  }

  // 卸载后停止定时保存，不在离开时发起无法确认的请求。
  function dispose(): void { disposed = true; suspendPresence(); }

  return { document, error, saveError, conflict, connectionError, saving, operation, dirtyCount, editable,
    start, resumePresence, suspendPresence, changeSentence, resetSentence, renameSpeaker, addSpeaker, flush, retry, exportDocuments, selectAudio, prepareAudio, dispose };
}
