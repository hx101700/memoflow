<script setup lang="ts">
import { ElButton, ElIcon, ElTag, vLoading } from "element-plus";
import { Document, DocumentChecked } from "@element-plus/icons-vue";
import { fileSize, type Translate } from "../i18n";
import type { AudioSelection } from "../types";

defineProps<{ audio: AudioSelection | null; disabled: boolean; selecting: boolean; requirements: string; supportedFormats: string; t: Translate }>();
const emit = defineEmits<{ select: [] }>();
</script>

<template>
  <div class="audio-field" :aria-busy="selecting">
    <div v-loading="selecting">
      <ElButton class="file-choice" plain :disabled="disabled" :aria-label="t(audio ? 'replaceAudio' : 'chooseAudio')" @click="emit('select')">
        <span class="file-choice-content">
          <ElIcon :size="32" :color="audio ? 'var(--el-color-success)' : undefined" aria-hidden="true"><component :is="audio ? DocumentChecked : Document" /></ElIcon>
          <strong class="audio-name">{{ audio ? audio.name : t('chooseAudio') }}</strong>
          <span v-if="audio" class="audio-selection" role="status" aria-live="polite">
            <ElTag size="small" type="success" effect="plain">{{ t('selectedBadge') }}</ElTag>
            <span>{{ fileSize(audio.size_bytes) }} · {{ t('replaceAudio') }}</span>
          </span>
          <span class="helper">{{ requirements }}<br>{{ supportedFormats }}</span>
        </span>
      </ElButton>
    </div>
    <p v-if="audio" class="helper audio-path">{{ audio.path }}</p>
  </div>
</template>
