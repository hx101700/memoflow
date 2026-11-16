<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { ElAlert, ElButton, ElDialog, ElConfigProvider, ElIcon, ElInput, ElOption, ElScrollbar, ElSelect, ElSlider, ElSwitch } from "element-plus";
import { Download, User } from "@element-plus/icons-vue";
import en from "element-plus/es/locale/lang/en";
import zhCn from "element-plus/es/locale/lang/zh-cn";
import { durationText, localize, type Translate } from "./i18n";
import { usePreferences } from "./preferences";
import { useReview } from "./useReview";
import { sentenceModified } from "./review";
import type { Language, ReviewApi, ReviewSentence as Sentence } from "./types";
import AppHeader from "./components/AppHeader.vue";
import ReviewSentence from "./components/ReviewSentence.vue";

const props = defineProps<{ connect: (language: () => Language, t: Translate) => ReviewApi }>();
const { language, theme, t } = usePreferences("reviewTitlePage");
const review = useReview(props.connect(() => language.value, t), t);
const { document: draft, error, saveError, conflict, connectionError, saving, operation, dirtyCount, editable, stale } = review;
const locale = computed(() => language.value === "en" ? en : zhCn);
const audio = ref<HTMLAudioElement>();
const playerKey = ref(0);
const audioReady = ref(false);
const playing = ref(false);
const position = ref(0);
const scrubPosition = ref<number | null>(null);
const duration = ref(0);
const rate = ref(1);
const follow = ref(true);
const namesOpen = ref(false);
const speakerScroll = ref<InstanceType<typeof ElScrollbar>>();
const speakerList = ref<HTMLDivElement>();
const currentIndex = ref<number | null>(null);
const modifiedSentences = computed(() => draft.value?.sentences.filter(sentenceModified) ?? []);
let lastModifiedIndex = 0;
const audioError = ref<"reviewAudioUnsupported" | "reviewAudioNetwork" | "reviewPlayBlocked" | null>(null);
let stopAt: number | null = null;
let prepared = false;
let frame = 0;
let stopTimer: ReturnType<typeof setTimeout> | undefined;
const audioUrl = computed(() => `/api/review/audio?v=${playerKey.value}`);
const displayedPosition = computed(() => scrubPosition.value ?? position.value);
const audioProblem = computed(() => audioError.value ? t(audioError.value) : draft.value?.audio.error ? localize(draft.value.audio.error, language.value) : t("reviewAudioMissing"));
const playable = computed(() => Boolean(draft.value?.audio.available && !draft.value.closed && !audioError.value));
const audioUnavailable = computed(() => Boolean(draft.value && (!draft.value.audio.available || audioError.value)));
// 所有结果共用同一提示区域，错误优先于音频和导出信息。
const notice = computed<{ type: "error" | "warning" | "info" | "success"; text: string; action?: "retry" | "connect" | "audio" }>(() => {
  if (saveError.value) return { type: "error", text: saveError.value.describe(language.value), action: conflict.value ? undefined : "retry" };
  if (connectionError.value) return { type: "error", text: t("reviewNetwork"), action: "connect" };
  if (error.value) return { type: "error", text: error.value.describe(language.value), action: audioUnavailable.value && !conflict.value ? "audio" : undefined };
  if (operation.value === "prepare") return { type: "info", text: t("reviewAudioPreparing") };
  if (audioUnavailable.value) return { type: "warning", text: audioProblem.value, action: "audio" };
  if (draft.value?.delivery && draft.value.delivery.status !== "COMPLETE") return { type: "warning", text: t(draft.value.delivery.status === "PARTIAL" ? "reviewExportPartial" : "reviewExportFailed") };
  if (saving.value || dirtyCount.value) return { type: "info", text: t(saving.value ? "reviewSaving" : "reviewUnsaved") };
  if (stale.value) return { type: "warning", text: t("reviewExportStale") };
  if (draft.value?.delivery?.status === "COMPLETE") return { type: "success", text: t("reviewExported") };
  return { type: "info", text: t(draft.value ? "reviewSaved" : "loading") };
});

// 定位页首标题，保持两个页面一致的品牌导航。
function focusTitle(): void { window.document.getElementById("page-title")?.focus(); window.scrollTo({ top: 0 }); }

// 新增后滚动到列表末尾并定位名称输入，保留弹窗底部操作的位置。
async function addSpeaker(): Promise<void> {
  if (!editable.value) return;
  review.addSpeaker();
  await nextTick();
  speakerScroll.value?.setScrollTop(speakerList.value?.scrollHeight ?? 0);
  speakerList.value?.querySelector<HTMLInputElement>("label:last-child input")?.focus({ preventScroll: true });
}

// 按原句顺序循环定位改动，暂停回听并把焦点交给目标正文，便于直接校对。
async function nextModification(): Promise<void> {
  const sentence = modifiedSentences.value.find(row => row.index > lastModifiedIndex) ?? modifiedSentences.value[0];
  if (!sentence) return;
  audio.value?.pause();
  lastModifiedIndex = sentence.index;
  const row = window.document.getElementById(`review-sentence-${sentence.index}`);
  row?.querySelector<HTMLElement>(".review-paragraph")?.focus({ preventScroll: true });
  await nextTick();
  row?.scrollIntoView({ block: "center" });
}

// 检查当前是否正在编辑，播放跟随不能移动正在输入的行。
function isEditing(): boolean { return Boolean(window.document.activeElement?.closest(".review-text-editor, .review-speaker-picker, .review-speaker-list")); }

// 按真实播放时间定位当前句，间隔定位到下一句，录音末尾保留最后一句。
function locateSentence(seconds: number): void {
  const rows = draft.value?.sentences ?? [];
  const milliseconds = seconds * 1000;
  const sentence = rows.find(row => row.begin_ms <= milliseconds && row.end_ms > milliseconds)
    ?? rows.find(row => row.begin_ms >= milliseconds) ?? rows.at(-1);
  currentIndex.value = sentence?.index ?? null;
}

// 跟随音频当前位置标记句子，连续播放与跳转均沿原始句子顺序显示。
function updatePosition(): void {
  const element = audio.value;
  if (!element) return;
  if (stopAt !== null && element.currentTime >= stopAt) {
    const end = stopAt;
    element.pause();
    element.currentTime = end;
    stopAt = null;
    position.value = end;
    return;
  }
  position.value = element.currentTime;
  // 单句结束后的 timeupdate 仍可能到达；暂停时保留刚听完的句子。
  if (!element.paused) locateSentence(position.value);
}

// 用浏览器时钟与短定时器共同控制单句结束，隐藏页面也不会继续整段播放。
function scheduleStop(): void {
  clearTimeout(stopTimer);
  const element = audio.value;
  if (!element || element.paused || stopAt === null) return;
  stopTimer = setTimeout(() => { updatePosition(); scheduleStop(); }, Math.max(10, (stopAt - element.currentTime) * 1000 / element.playbackRate));
}

// 播放时逐帧更新高亮和进度，暂停时取消页面时钟。
function tick(): void {
  updatePosition();
  if (audio.value && !audio.value.paused) frame = requestAnimationFrame(tick);
}

// 同步原生播放器的实际播放状态。
function onPlay(): void { playing.value = true; cancelAnimationFrame(frame); tick(); scheduleStop(); }

// 暂停后停止时钟并保留当前位置。
function onPause(): void { playing.value = false; cancelAnimationFrame(frame); clearTimeout(stopTimer); }

// 加载媒体元信息并恢复倍速。
function loaded(): void {
  if (!audio.value) return;
  duration.value = Number.isFinite(audio.value.duration) ? audio.value.duration : 0;
  audio.value.playbackRate = rate.value;
  audioReady.value = true;
}

// 开始播放，浏览器拒绝播放时显示可恢复说明。
async function play(): Promise<void> {
  if (!playable.value || !audio.value) return;
  try { await audio.value.play(); }
  catch (reason) {
    if (reason instanceof DOMException && reason.name === "NotSupportedError") await mediaFailed(true);
    else if (!(reason instanceof DOMException && reason.name === "AbortError")) audioError.value = "reviewPlayBlocked";
  }
}

// 回听所选句子的完整片段，到该句结束时间暂停。
async function playSentence(sentence: Sentence): Promise<void> {
  if (!playable.value || !audio.value) return;
  audio.value.pause();
  currentIndex.value = sentence.index;
  audio.value.currentTime = sentence.begin_ms / 1000;
  position.value = audio.value.currentTime;
  stopAt = sentence.end_ms / 1000;
  await play();
}

// 底部播放器从当前位置连续播放，暂停后保留位置。
async function togglePlay(): Promise<void> {
  const element = audio.value;
  if (!element) return;
  if (!element.paused) { element.pause(); return; }
  stopAt = null;
  await play();
}

// 拖动时只更新滑块预览，避免播放时钟把用户的拖动位置拉回。
function previewSeek(value: number | number[]): void {
  if (!Array.isArray(value)) scrubPosition.value = value;
}

// 用户释放滑块或点击快进后跳转；暂停时也立即定位并高亮对应句子。
function seek(value: number | number[]): void {
  if (!audio.value || Array.isArray(value)) return;
  audio.value.currentTime = Math.max(0, Math.min(duration.value, value));
  position.value = audio.value.currentTime;
  scrubPosition.value = null;
  stopAt = null;
  clearTimeout(stopTimer);
  locateSentence(position.value);
}

// 仅在浏览器明确不支持或解码失败时请求一次播放副本，网络失败不会自动转换。
async function mediaFailed(unsupported = false): Promise<void> {
  const code = unsupported ? 4 : audio.value?.error?.code;
  audioReady.value = false;
  onPause();
  if ((code === 3 || code === 4) && !prepared && draft.value?.audio.kind !== "preview") {
    // 浏览器也会把404等加载失败报告为不支持；先核对同一音频端点可读，避免网络故障触发转码。
    try {
      const response = await fetch(audioUrl.value, { method: "HEAD", credentials: "same-origin", cache: "no-store" });
      if (!response.ok) { audioError.value = "reviewAudioNetwork"; return; }
    } catch { audioError.value = "reviewAudioNetwork"; return; }
    prepared = true;
    if (await review.prepareAudio()) { reloadAudio(); return; }
  }
  audioError.value = code === 3 || code === 4 ? "reviewAudioUnsupported" : "reviewAudioNetwork";
}

// 更新音频地址以重新加载已绑定原文件或复用的播放副本。
function reloadAudio(): void {
  audioError.value = null;
  audioReady.value = false;
  position.value = 0;
  scrubPosition.value = null;
  currentIndex.value = null;
  stopAt = null;
  playerKey.value += 1;
}

// 保存修改并选择录音，成功后重新加载播放器。
async function selectAudio(): Promise<void> {
  audio.value?.pause();
  if (await review.selectAudio()) { prepared = false; reloadAudio(); }
}

// 未保存或保存中离开时使用浏览器标准提示，防止静默丢失输入。
function beforeUnload(event: BeforeUnloadEvent): void {
  if (dirtyCount.value || saving.value) { event.preventDefault(); event.returnValue = ""; }
}

watch([currentIndex, follow], async ([index, enabled]) => {
  if (!enabled || isEditing() || index === null) return;
  await nextTick();
  if (!isEditing()) window.document.getElementById(`review-sentence-${index}`)?.scrollIntoView({ block: "nearest" });
});
watch(rate, value => { if (audio.value) audio.value.playbackRate = value; scheduleStop(); });
watch(() => draft.value?.closed, closed => { if (closed) audio.value?.pause(); });
// 离页仅关闭在场连接，让服务端宽限期覆盖刷新与短暂导航。
function pageHidden(): void { audio.value?.pause(); review.suspendPresence(); }

// 从浏览器往返缓存恢复时重新登记在场，不重建草稿或覆盖未保存输入。
function pageShown(event: PageTransitionEvent): void { if (event.persisted) review.resumePresence(); }

onMounted(() => {
  window.addEventListener("beforeunload", beforeUnload);
  window.addEventListener("pagehide", pageHidden);
  window.addEventListener("pageshow", pageShown);
  void review.start();
});
onUnmounted(() => {
  audio.value?.pause(); cancelAnimationFrame(frame); clearTimeout(stopTimer); review.dispose();
  window.removeEventListener("beforeunload", beforeUnload);
  window.removeEventListener("pagehide", pageHidden);
  window.removeEventListener("pageshow", pageShown);
});
</script>

<template>
  <ElConfigProvider :locale="locale" size="default">
    <div class="review-layout">
      <AppHeader v-model:language="language" v-model:theme="theme" :version="draft?.skill_version" :t="t" @home="focusTitle" />
      <main class="page-shell review-page">
        <div class="review-heading">
          <div class="review-heading-copy">
            <h1 id="page-title" tabindex="-1">{{ t('reviewTitlePage') }}</h1>
          </div>
          <div v-if="draft && !draft.closed" class="review-action-buttons">
            <span class="review-file">{{ draft.source_name }}</span>
            <div class="review-header-buttons">
              <ElButton :icon="User" :disabled="!editable" @click="namesOpen = true">{{ t('reviewSpeakers') }}</ElButton>
              <ElButton type="primary" :icon="Download" :disabled="!editable || Boolean(saveError)" :loading="operation === 'export'" @click="review.exportDocuments">{{ t('reviewExport') }}</ElButton>
            </div>
          </div>
        </div>
        <div id="review-notice" class="review-notice" role="status" aria-live="polite">
          <ElAlert :title="notice.text" :type="notice.type" :closable="false" show-icon>
            <ElButton v-if="notice.action === 'retry'" :loading="saving" @click="review.retry">{{ t('reviewRetry') }}</ElButton>
            <ElButton v-else-if="notice.action === 'connect'" @click="review.resumePresence">{{ t('reviewReconnect') }}</ElButton>
            <ElButton v-else-if="notice.action === 'audio'" :disabled="!editable || saving" @click="selectAudio">{{ t('reviewAudioSelect') }}</ElButton>
          </ElAlert>
        </div>
        <template v-if="draft && !draft.closed">
          <div class="review-reading-frame">
            <div class="review-reading-list" :aria-label="t('reviewText')">
              <ReviewSentence v-for="sentence in draft.sentences" :key="sentence.index" :sentence="sentence" :speakers="draft.speakers"
                :disabled="!editable" :playable="playable && audioReady" :current="currentIndex === sentence.index" :t="t"
                @text="review.changeSentence(sentence.index, { text: $event })" @speaker="review.changeSentence(sentence.index, { speaker_id: $event })"
                @reset="review.resetSentence(sentence.index)" @play="playSentence(sentence)" @blur="review.flush" />
            </div>
          </div>
          <section class="review-toolbar" :aria-label="t('reviewProgress')">
            <audio v-if="draft.audio.available" :key="playerKey" ref="audio" :src="audioUrl" preload="metadata" @loadedmetadata="loaded" @error="mediaFailed()" @play="onPlay" @pause="onPause" @timeupdate="updatePosition" @ended="onPause" />
            <div class="review-player-controls">
              <ElButton class="review-play-toggle" type="primary" :disabled="!playable || !audioReady" :aria-label="t(playing ? 'reviewPause' : 'reviewPlay')" @click="togglePlay">
                <ElIcon :size="18" aria-hidden="true"><svg viewBox="0 0 24 24" fill="currentColor"><template v-if="playing"><rect x="6" y="5" width="4" height="14" /><rect x="14" y="5" width="4" height="14" /></template><path v-else d="M8 5l11 7-11 7z" /></svg></ElIcon>
              </ElButton>
              <ElButton class="review-skip" :disabled="!playable || !audioReady" :aria-label="t('reviewBack')" @click="seek(position - 5)">−5s</ElButton>
              <ElButton class="review-skip" :disabled="!playable || !audioReady" :aria-label="t('reviewForward')" @click="seek(position + 5)">+5s</ElButton>
              <div class="review-progress"><span>{{ durationText(displayedPosition) }}</span><ElSlider :model-value="displayedPosition" :max="duration || 1" :step="0.01" :show-tooltip="false" :disabled="!playable || !audioReady" :aria-label="t('reviewProgress')" @input="previewSeek" @change="seek" /><span>{{ durationText(duration) }}</span></div>
              <ElSelect v-model="rate" :aria-label="t('reviewSpeed')" class="review-speed"><ElOption v-for="speed in [0.5, 0.75, 1, 1.25, 1.5, 2]" :key="speed" :value="speed" :label="`${speed}×`" /></ElSelect>
              <ElSwitch v-model="follow" :active-text="t('reviewFollow')" :aria-label="t('reviewFollow')" />
              <ElButton :disabled="!modifiedSentences.length || Boolean(operation)" @click="nextModification">{{ t('reviewNextModified') }}</ElButton>
            </div>
          </section>
          <ElDialog v-model="namesOpen" :title="t('reviewSpeakers')" width="min(560px, calc(100vw - 32px))" align-center @closed="review.flush">
            <p class="helper">{{ t('reviewRenameHint') }}</p>
            <ElScrollbar ref="speakerScroll" class="review-speaker-scroll" max-height="min(360px, 50vh)">
              <div ref="speakerList" class="review-speaker-list"><label v-for="speaker in draft.speakers" :key="speaker.id">{{ t('reviewSpeakerName', { id: speaker.id }) }}<ElInput :model-value="speaker.name" :placeholder="t('reviewSpeakerName', { id: speaker.id })" :readonly="!editable" @update:model-value="review.renameSpeaker(speaker.id, $event)" @blur="review.flush" /></label></div>
            </ElScrollbar>
            <template #footer><ElButton :disabled="!editable" @click="addSpeaker">{{ t('reviewAddSpeaker') }}</ElButton><ElButton type="primary" @click="namesOpen = false">{{ t('reviewDone') }}</ElButton></template>
          </ElDialog>
        </template>
      </main>
    </div>
  </ElConfigProvider>
</template>
