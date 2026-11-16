<script setup lang="ts">
import { computed, nextTick, ref } from "vue";
import { ElButton, ElCard, ElInput, ElOption, ElSelect, ElTag } from "element-plus";
import { Clock, RefreshLeft } from "@element-plus/icons-vue";
import { durationText, type Translate } from "../i18n";
import { sentenceModified } from "../review";
import type { ReviewSentence, ReviewSpeaker } from "../types";

const props = defineProps<{ sentence: ReviewSentence; speakers: ReviewSpeaker[]; disabled: boolean; playable: boolean; current: boolean; t: Translate }>();
const emit = defineEmits<{ text: [value: string]; speaker: [value: number | null]; reset: []; play: []; blur: [] }>();
const editing = ref(false);
const choosingSpeaker = ref(false);
const input = ref<InstanceType<typeof ElInput>>();
const select = ref<InstanceType<typeof ElSelect>>();
const modified = computed(() => sentenceModified(props.sentence));
const speakerName = computed(() => props.sentence.speaker_id === null ? props.t("reviewUnassigned") :
  props.speakers.find(speaker => speaker.id === props.sentence.speaker_id)?.name || props.t("reviewSpeakerName", { id: props.sentence.speaker_id }));

// 将阅读段落切换为原位输入，完整展开正文并保留同一句组件身份。
async function editText(event: MouseEvent | KeyboardEvent): Promise<void> {
  if (props.disabled) return;
  let offset = props.sentence.text.length;
  if (event instanceof MouseEvent) {
    const caret = document.caretPositionFromPoint(event.clientX, event.clientY);
    if (caret?.offsetNode === (event.currentTarget as HTMLElement).firstChild) offset = caret.offset;
  }
  editing.value = true;
  await nextTick();
  const editor = input.value?.textarea;
  editor?.focus({ preventScroll: true });
  editor?.setSelectionRange(offset, offset);
}

// 失焦回到正文阅读视图，并立即保存已经输入的内容。
function finishText(): void { editing.value = false; emit("blur"); }

// 按需创建说话人选择器，避免长列表为每句常驻重型下拉组件。
async function chooseSpeaker(): Promise<void> {
  if (props.disabled) return;
  choosingSpeaker.value = true;
  await nextTick();
  select.value?.focus();
}

// 下拉收起后恢复说话人标签并保存归属。
function speakerVisible(visible: boolean): void {
  if (!visible) { choosingSpeaker.value = false; emit("blur"); }
}
</script>

<template>
  <ElCard :id="`review-sentence-${sentence.index}`" class="review-sentence" :class="{ 'is-modified': modified, 'is-current': current, 'is-editing': editing }"
    shadow="never" body-class="review-sentence-body" role="article"
    :aria-label="t('reviewSentence', { index: sentence.index })" :aria-current="current ? 'true' : undefined">
    <div class="review-sentence-meta">
      <ElSelect v-if="choosingSpeaker" ref="select" class="review-speaker-picker" :model-value="sentence.speaker_id ?? -1" automatic-dropdown
        :disabled="disabled" :aria-label="t('reviewSentence', { index: sentence.index }) + ' · ' + t('reviewSpeaker')"
        @update:model-value="emit('speaker', $event === -1 ? null : $event)" @visible-change="speakerVisible">
        <ElOption :value="-1" :label="t('reviewUnassigned')" />
        <ElOption v-for="speaker in speakers" :key="speaker.id" :value="speaker.id" :label="speaker.name || t('reviewSpeakerName', { id: speaker.id })" />
      </ElSelect>
      <ElButton v-else class="review-speaker-label" text :disabled="disabled" :aria-label="t('reviewSentence', { index: sentence.index }) + ' · ' + t('reviewSpeaker')" @click="chooseSpeaker">{{ speakerName }}</ElButton>
      <ElButton class="review-timecode" text :icon="Clock" :disabled="!playable" :aria-label="t('reviewPlaySentence', { index: sentence.index })" @click="emit('play')">{{ durationText(sentence.begin_ms / 1000) }} – {{ durationText(sentence.end_ms / 1000) }}</ElButton>
      <ElTag v-if="modified" size="small" type="success" effect="plain">{{ t('reviewModified') }}</ElTag>
      <ElButton class="review-reset" text :icon="RefreshLeft" :disabled="disabled || !modified" :aria-label="t('reviewResetSentence', { index: sentence.index })" @click="emit('reset')">{{ t('reviewReset') }}</ElButton>
    </div>
    <ElInput v-if="editing" ref="input" class="review-text-editor" :model-value="sentence.text" type="textarea" :autosize="{ minRows: 1 }" resize="none" :readonly="disabled"
      :aria-label="t('reviewSentence', { index: sentence.index }) + ' · ' + t('reviewText')" @update:model-value="emit('text', $event)" @blur="finishText" />
    <div v-else class="review-paragraph" role="button" :tabindex="disabled ? -1 : 0" :aria-label="t('reviewEditSentence', { index: sentence.index })"
      @click="editText" @keydown.enter.prevent="editText" @keydown.space.prevent="editText">{{ sentence.text || t('reviewEmptyText') }}</div>
  </ElCard>
</template>
