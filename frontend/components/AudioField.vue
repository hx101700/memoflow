<script setup lang="ts">
import { ElButton, ElTag } from "element-plus";
import { FolderOpened } from "@element-plus/icons-vue";
import { fileSize, type Translate } from "../i18n";
import type { AudioSelection } from "../types";

defineProps<{ audio: AudioSelection | null; disabled: boolean; selecting: boolean; t: Translate }>();
const emit = defineEmits<{ select: [] }>();
</script>

<template>
  <div class="audio-field" :aria-busy="selecting">
    <ElButton :icon="FolderOpened" :disabled="disabled" :loading="selecting" @click="emit('select')">
      {{ t(audio ? 'replaceAudio' : 'chooseAudio') }}
    </ElButton>
    <div class="audio-selection" role="status" aria-live="polite">
      <template v-if="audio">
        <ElTag size="small" type="info" effect="plain">{{ t('selectedBadge') }}</ElTag>
        <span>{{ audio.name }} · {{ fileSize(audio.size_bytes) }}</span>
      </template>
      <span v-else>{{ t('emptyAudio') }}</span>
    </div>
    <p v-if="audio" class="helper audio-path">{{ audio.path }}</p>
  </div>
</template>
