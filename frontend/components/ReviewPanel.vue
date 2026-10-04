<script setup lang="ts">
import { computed } from "vue";
import { ElAlert, ElCard, ElDescriptions, ElDescriptionsItem, ElDivider, ElTable, ElTableColumn } from "element-plus";
import { durationText, fileSize, languageName, type Translate } from "../i18n";
import type { Language, Model } from "../types";

const props = defineProps<{ model: Model; language: Language; t: Translate }>();

// 从已校验快照生成只读的音频、转写设置和保存位置。
const rows = computed<[string, string][]>(() => {
  const { model, t, language } = props;
  const preview = model.preview;
  if (!preview) return [];
  const { summary, configuration: config } = preview;
  const values: [string, string][] = [
    [t("audioFile"), summary.audio.name],
    [t("duration"), durationText(summary.audio.duration_seconds)],
    [t("fileSize"), fileSize(summary.audio.size_bytes)],
    [t("formatChannels"), `${summary.audio.format_name} / ${t(summary.audio.channels === 1 ? "channel" : "channels", { count: summary.audio.channels })}`],
    [t("sampleRate"), `${summary.audio.sample_rate.toLocaleString(language)} Hz`],
    [t("audioLanguage"), config.language_hint ? languageName(config.language_hint, language) : t("automatic")],
    [t("diarization"), t(config.diarization_enabled ? "enabled" : "disabled")],
  ];
  if (config.diarization_enabled) values.push([t("speakers"), config.speaker_count ? t("speakerValue", { count: config.speaker_count }) : t("automatic")]);
  values.push([t("connection"), config.auth_mode === "api_key" ? "API Key" : t("consoleLogin")],
    [t("modelRegion"), `${model.session?.model} · ${t("region")}`],
    [t("jsonLocation"), summary.json_directory], [t("documentLocation"), summary.document_directory]);
  return values;
});
</script>

<template>
  <ElCard v-if="model.preview" id="review" class="review-panel" shadow="never" header-class="panel-title" tabindex="-1" :aria-label="t('review')">
    <template #header><h2>{{ t('review') }}</h2></template>
    <ElDescriptions border :column="1" :label-width="148">
      <ElDescriptionsItem v-for="[label, value] in rows" :key="label" :label="label">{{ value }}</ElDescriptionsItem>
    </ElDescriptions>
    <ElAlert v-for="warning in model.preview.summary.warnings" :key="warning" :title="warning" type="warning" :closable="false" show-icon class="review-warning" />
    <ElDivider content-position="left">{{ t('hotwordsLabel') }}</ElDivider>
    <ElTable v-if="model.preview.configuration.hotword_rows.length" :data="model.preview.configuration.hotword_rows" border max-height="360" :aria-label="t('hotwordFile')">
      <ElTableColumn type="index" :label="t('rowNumber')" width="70" />
      <ElTableColumn prop="text" :label="t('textColumn')" />
      <ElTableColumn prop="weight" :label="t('weightColumn')" width="110" />
    </ElTable>
    <p v-else class="subtle">{{ t('disabled') }}</p>
    <ElDivider content-position="left">{{ t('contextLabel') }}</ElDivider>
    <p v-if="model.preview.configuration.context" class="preview-context">{{ model.preview.configuration.context }}</p>
    <p v-else class="subtle">{{ t('disabled') }}</p>
  </ElCard>
</template>
