<script setup lang="ts">
import { computed } from "vue";
import { ElCard, ElDescriptions, ElDescriptionsItem } from "element-plus";
import { fileSize, languageName, type Translate } from "../i18n";
import type { AudioSelection, FormValues, Language } from "../types";

const props = defineProps<{ audio: AudioSelection | null; form: FormValues; contextLength: number; language: Language; t: Translate }>();

// 从当前填写内容生成侧栏摘要，随表单和界面语言同步显示。
const rows = computed<[string, string][]>(() => {
  const { audio, form, contextLength, language, t } = props;
  return [
    [t("audioFile"), audio ? `${audio.name} · ${fileSize(audio.size_bytes)}` : t("noAudio")],
    [t("audioLanguage"), form.language ? languageName(form.language, language) : t("automatic")],
    [t("diarization"), t(form.diarizationEnabled ? "enabled" : "disabled")],
    [t("hotwordsLabel"), form.hotwordsEnabled ? t("hotwordRows", { count: form.hotwordRows.length }) : t("disabled")],
    [t("contextLabel"), form.contextEnabled ? t("contextCount", { count: contextLength }) : t("disabled")],
    [t("connection"), form.useApiKey ? "API Key" : t("consoleLogin")],
  ];
});
</script>

<template>
  <aside class="settings-summary" :aria-label="t('currentSettings')">
    <ElCard shadow="never" header-class="section-heading">
      <template #header><h2>{{ t('currentSettings') }}</h2></template>
      <ElDescriptions :column="1" :label-width="90">
        <ElDescriptionsItem v-for="([label, value], index) in rows" :key="index" :label="label" label-class-name="summary-label" class-name="summary-value">{{ value }}</ElDescriptionsItem>
      </ElDescriptions>
    </ElCard>
  </aside>
</template>
