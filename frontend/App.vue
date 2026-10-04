<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from "vue";
import { ElAlert, ElButton, ElCard, ElCollapse, ElCollapseItem, ElConfigProvider, ElDescriptions, ElDescriptionsItem, ElDivider, ElForm, ElFormItem, ElIcon, ElInput, ElMessage, ElOption, ElResult, ElSelect, ElStep, ElSteps, ElSwitch, ElTag } from "element-plus";
import { Aim, ChatLineSquare, DocumentCopy, Edit, FolderOpened, Headset, Key, Monitor, Moon, Reading, Setting, Sunny, View } from "@element-plus/icons-vue";
import en from "element-plus/es/locale/lang/en";
import zhCn from "element-plus/es/locale/lang/zh-cn";
import { availability } from "./model";
import { languageName, type Translate } from "./i18n";
import { usePreferences } from "./preferences";
import { useTranscription } from "./useTranscription";
import type { Api, DirectoryKind, Language } from "./types";
import KeyDisplay from "./components/KeyDisplay.vue";
import ReviewPanel from "./components/ReviewPanel.vue";
import UploadField from "./components/UploadField.vue";
import HotwordEditor from "./components/HotwordEditor.vue";

const props = defineProps<{ connect: (language: () => Language, t: Translate) => Api }>();
const { language, theme, t } = usePreferences();
const keyDisplay = ref<InstanceType<typeof KeyDisplay>>();
const hotwordEditor = ref<InstanceType<typeof HotwordEditor>>();
const aliases: Record<string, string> = { audio_path: "audio_upload_id" };

// 在控件完成渲染后定位错误字段或当前操作区域。
async function focus(target: string): Promise<void> {
  await nextTick();
  const region = document.getElementById(aliases[target] ?? target) ?? document.getElementById("error-panel");
  if (!region) return;
  if (target === "hotword_rows" && hotwordEditor.value) {
    await hotwordEditor.value?.focusRow();
    return;
  }
  const control = Array.from(region.querySelectorAll<HTMLElement>(
    'input:not(:disabled), textarea:not(:disabled), button:not(:disabled), [role="button"][tabindex="0"]',
  )).find(element => element.getClientRects().length > 0);
  (control ?? region).focus({ preventScroll: true });
  if (["review", "config-fields", "session-ended"].includes(target)) window.scrollTo({ top: 0, behavior: "auto" });
  else region.scrollIntoView({ block: "center", behavior: "auto" });
}

// 将已取得的模板交给浏览器下载。
function download(blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "hotwords-template.xlsx";
  link.click();
  URL.revokeObjectURL(url);
}

const { model, form, error, actions } = useTranscription(props.connect(() => language.value, t), {
  focus: target => { void focus(target); },
  setApiKey: value => keyDisplay.value?.setValue(value),
  getApiKey: () => keyDisplay.value?.getValue() ?? "",
  download,
}, t);
const available = computed(() => availability(model));
const locale = computed(() => language.value === "en" ? en : zhCn);
const terminal = computed(() => ["handed_off", "expired", "cancelled"].includes(model.phase));
const step = computed(() => model.preview ? 1 : 0);
const confirmationText = computed(() => t("confirmationMessage", { id: model.session?.session_id ?? "" }));
const contextLength = computed(() => Array.from(form.context).length);
const outputKinds: DirectoryKind[] = ["json", "document"];

// 单独保存 Key 成功后显示本机保存回执。
async function saveApiKey(): Promise<void> {
  if (await actions.saveApiKey()) ElMessage.success(t("keySaved"));
}

// 复制带当前会话编号的确认文字，供用户在 Codex 中发起交接。
async function copyConfirmation(): Promise<void> {
  if (!available.value.copy) return;
  try {
    await navigator.clipboard.writeText(confirmationText.value);
    ElMessage.success(t("copied"));
  } catch { ElMessage.error(t("copyFailed")); }
}

// 将后端字段别名映射到当前页面的可访问输入区域。
function invalid(field: string): boolean {
  return Boolean(error.value && (aliases[error.value.field ?? ""] ?? error.value.field) === field);
}

// 读取输入位置的错误说明，供 Element Plus 表单关联。
function fieldMessage(field: string): string {
  return invalid(field) ? error.value?.message ?? "" : "";
}

onMounted(actions.start);
onUnmounted(actions.dispose);
</script>

<template>
  <ElConfigProvider :locale="locale">
    <a class="skip-link" href="#config-fields">{{ t('skip') }}</a>
    <header class="topbar">
      <div class="topbar-inner">
        <a class="brand" href="#" @click.prevent="focus('page-title')">
          <ElIcon class="brand-mark" :size="22" aria-hidden="true"><Headset /></ElIcon>
          <span>MemoFlow</span>
        </a>
        <div class="appearance-controls">
          <ElSelect id="interface-language" v-model="language" :aria-label="t('language')" :disabled="!available.changeLanguage" @change="actions.languageChanged" class="language-select">
            <ElOption value="zh-CN" label="简体中文" /><ElOption value="en" label="English" />
          </ElSelect>
          <ElSelect id="theme" v-model="theme" :aria-label="t('theme')" class="theme-select">
            <template #prefix><ElIcon :size="16" aria-hidden="true"><component :is="theme === 'system' ? Monitor : theme === 'light' ? Sunny : Moon" /></ElIcon></template>
            <ElOption value="system" :label="t('system')" /><ElOption value="light" :label="t('light')" /><ElOption value="dark" :label="t('dark')" />
          </ElSelect>
        </div>
      </div>
    </header>

    <main class="page-shell">
      <div class="intro">
        <div><div class="page-title-row">
          <h1 id="page-title" tabindex="-1">{{ t('title') }}</h1>
          <ElTag size="small" type="info" effect="plain">{{ t('preview') }}</ElTag></div>
          <p>{{ terminal ? t('endedLocal') : t('intro') }}</p>
        </div>
        <span class="region"><span aria-hidden="true">●</span>{{ t('region') }}</span>
      </div>

      <ElSteps v-if="!terminal" :active="step" finish-status="success" class="steps" align-center>
        <ElStep :title="t('stepConfigure')" /><ElStep :title="t('stepReview')" />
      </ElSteps>
      <ElAlert v-if="!terminal && !model.preview" :title="t('beforeStart')" type="info" :closable="false" show-icon class="intro-note" />
      <ElAlert v-if="model.statusMessage" :title="t(model.statusMessage)" type="info" :closable="false" show-icon class="page-notice" />
      <ElAlert v-if="error && !['hotword_rows', 'context'].includes(error.field ?? '')" id="error-panel" tabindex="-1" class="page-notice" :title="error.message" type="error" :closable="false" show-icon />
      <p v-if="model.phase === 'loading'" class="loading-note" role="status">{{ t('loading') }}</p>
      <ElAlert v-if="model.phase === 'unavailable'" :title="t('unavailable')" type="error" :closable="false" />

      <ElCard v-if="terminal" id="session-ended" class="receipt" shadow="never" tabindex="-1">
        <ElResult :icon="model.phase === 'handed_off' ? 'success' : 'info'"
          :title="t(model.phase === 'handed_off' ? 'handedOffTitle' : model.phase === 'expired' ? 'expiredTitle' : 'cancelledTitle')"
          :sub-title="t(model.phase === 'handed_off' ? 'handedOffHelp' : model.phase === 'expired' ? 'expiredHelp' : 'cancelledHelp')" />
        <ElDescriptions v-if="model.receipt" :column="1" direction="vertical">
          <ElDescriptionsItem :label="t('job')">{{ model.receipt.job_id }}</ElDescriptionsItem>
          <ElDescriptionsItem :label="t('jsonLocation')">{{ model.receipt.json_directory }}</ElDescriptionsItem>
          <ElDescriptionsItem :label="t('documentLocation')">{{ model.receipt.document_directory }}</ElDescriptionsItem>
        </ElDescriptions>
      </ElCard>

      <section v-else-if="model.preview" class="preview-view">
        <ReviewPanel :model="model" :language="language" :t="t" />
        <ElCard class="handoff-panel" shadow="never">
          <p>{{ t('uploadDisclosure') }}</p>
          <p class="helper">{{ t('reviewHelp') }}</p>
          <ElInput :model-value="confirmationText" readonly :aria-label="t('confirmationLabel')" class="confirmation-text" />
          <p class="helper">{{ t('expiryHelp') }}</p>
        </ElCard>
      </section>

      <div v-else-if="model.session && available.editable" class="workspace">
        <ElForm id="config-fields" :disabled="!available.editable" label-position="top" inline-message class="form-column" tabindex="-1" @submit.prevent="actions.validate">
          <ElCard id="audio_upload_id" shadow="never" header-class="section-heading" :class="{ 'needs-attention': invalid('audio_upload_id') }" tabindex="-1">
            <template #header><ElIcon class="section-icon" :size="20" aria-hidden="true"><Headset /></ElIcon><h2>{{ t('audioHeading') }}</h2><span class="section-aside">{{ t('oneFile') }}</span></template>
            <UploadField :upload="model.uploads.audio" :disabled="!available.upload.audio" :accept="model.session.audio_suffixes.join(',')" :t="t" @select="actions.upload('audio', $event)" />
            <p v-if="invalid('audio_upload_id')" class="field-error">{{ error?.message }}</p>
            <ElCollapse class="format-help">
              <ElCollapseItem :title="t('formatLimits')" name="formats"><p>{{ t('audioLimits', {
                size: model.session.limits.audio_bytes / 1_000_000_000, hours: model.session.limits.audio_seconds / 3600,
                upload: model.session.limits.upload_bytes / 1_000_000_000, formats: model.session.audio_suffixes.map(s => s.slice(1).toUpperCase()).join(', ') }) }}</p></ElCollapseItem>
            </ElCollapse>
          </ElCard>

          <ElCard id="settings" shadow="never" header-class="section-heading" tabindex="-1">
            <template #header><ElIcon class="section-icon" :size="20" aria-hidden="true"><Setting /></ElIcon><h2>{{ t('settings') }}</h2></template>
            <div id="language_hint" :class="{ 'needs-attention': invalid('language_hint') }" tabindex="-1">
              <ElFormItem :label="t('audioLanguage')" for="audio-language" :error="fieldMessage('language_hint')">
                <ElSelect id="audio-language" v-model="form.language" :empty-values="[null, undefined]" filterable @change="actions.changed()">
                  <ElOption value="" :label="t('automatic')" /><ElOption v-for="code in model.session.languages" :key="code" :value="code" :label="languageName(code, language)" />
                </ElSelect>
              </ElFormItem>
            </div>
            <div class="toggle-row">
              <div><label for="diarization">{{ t('diarization') }}</label><p>{{ t('diarizationHelp') }}</p></div>
              <ElSwitch id="diarization" v-model="form.diarizationEnabled" :aria-label="t('diarization')" @change="actions.changed()" />
            </div>
            <div v-if="form.diarizationEnabled" class="expanded-option">
              <p class="helper">{{ t('monoHelp') }}</p>
              <div id="speaker_count" :class="{ 'needs-attention': invalid('speaker_count') }" tabindex="-1">
                <ElFormItem :label="t('speakers') + ' · ' + t('optional')" for="speaker-count" :error="fieldMessage('speaker_count')">
                  <ElInput id="speaker-count" v-model="form.speaker" inputmode="numeric" :placeholder="t('automatic')" @input="actions.changed()" />
                </ElFormItem>
                <p class="helper">{{ t('speakerHint', { min: model.session.limits.speaker_min, max: model.session.limits.speaker_max }) }}</p>
              </div>
            </div>
          </ElCard>

          <ElCard id="enhancement" shadow="never" header-class="section-heading" tabindex="-1">
            <template #header><ElIcon class="section-icon" :size="20" aria-hidden="true"><Aim /></ElIcon><h2>{{ t('enhancement') }}</h2></template>
            <p class="section-description">{{ t('enhancementHint') }}</p>
            <div class="enhancement-option">
              <div class="toggle-row">
                <div><label for="hotwords-enabled"><ElIcon :size="16" aria-hidden="true"><Reading /></ElIcon>{{ t('hotwords') }}</label><p>{{ t('hotwordsHelp') }}</p></div>
                <ElSwitch id="hotwords-enabled" v-model="form.hotwordsEnabled" :aria-label="t('hotwords')" @change="actions.changed()" />
              </div>
              <div v-if="form.hotwordsEnabled" id="hotword_rows" class="expanded-option" :class="{ 'needs-attention': invalid('hotword_rows') }" tabindex="-1">
                <HotwordEditor ref="hotwordEditor" :rows="form.hotwordRows" :validation="model.hotwords" :upload="model.uploads.hotwords"
                  :disabled="!available.editHotwords" :template-disabled="!available.template" :downloading="model.downloadingTemplate"
                  :message="fieldMessage('hotword_rows')" :limit="model.session.limits.hotwords_count"
                  :file-limit="model.session.limits.hotwords_bytes / 1_000_000" :t="t"
                  @upload="actions.upload('hotwords', $event)" @download="actions.downloadTemplate" @add="actions.addHotword"
                  @remove="actions.removeHotword" @change="actions.changeHotword" @leave="actions.checkHotwords" />
              </div>
            </div>
            <ElDivider />
            <div class="enhancement-option">
              <div class="toggle-row">
                <div><label for="context-enabled"><ElIcon :size="16" aria-hidden="true"><ChatLineSquare /></ElIcon>{{ t('context') }}</label><p>{{ t('contextHelp') }}</p></div>
                <ElSwitch id="context-enabled" v-model="form.contextEnabled" :aria-label="t('context')" @change="actions.changed()" />
              </div>
              <div v-if="form.contextEnabled" id="context" class="expanded-option" :class="{ 'needs-attention': invalid('context') }" tabindex="-1">
                <ElFormItem :label="t('reference')" for="context-text" :error="fieldMessage('context')">
                  <ElInput id="context-text" v-model="form.context" type="textarea" :autosize="{ minRows: 4, maxRows: 10 }" :placeholder="t('contextPlaceholder')" @input="actions.changed()" />
                </ElFormItem>
                <div class="textarea-footer"><p class="helper">{{ t('contextHint', { count: model.session.limits.context_chars }) }}</p><span :class="{ 'field-error': contextLength > model.session.limits.context_chars }">{{ contextLength }} / {{ model.session.limits.context_chars }}</span></div>
              </div>
            </div>
          </ElCard>

          <ElCard id="outputs" shadow="never" header-class="section-heading" tabindex="-1">
            <template #header><ElIcon class="section-icon" :size="20" aria-hidden="true"><FolderOpened /></ElIcon><h2>{{ t('savingLocations') }}</h2></template>
            <div v-for="kind in outputKinds" :id="kind + '_directory'" :key="kind" class="output-field" :class="{ 'needs-attention': invalid(kind + '_directory') }" tabindex="-1">
              <div class="label-action"><label :for="kind + '-folder'">{{ t(kind === 'json' ? 'rawResult' : 'documents') }}</label>
                <ElButton v-if="model.directories[kind] !== 'default'" text :disabled="!available.chooseDirectory" @click="actions.resetDirectory(kind)">{{ t('resetFolder') }}</ElButton></div>
              <div class="directory-row"><ElInput :id="kind + '-folder'" :model-value="model.directories[kind] === 'default' ? '' : model.directories[kind]" :placeholder="model.session.output_defaults[kind]" :title="model.directories[kind] === 'default' ? model.session.output_defaults[kind] : model.directories[kind]" readonly />
                <ElButton :icon="FolderOpened" :disabled="!available.chooseDirectory" @click="actions.selectDirectory(kind)">{{ model.picker?.kind === kind ? t('choosingFolder') : t('chooseFolder') }}</ElButton></div>
              <p v-if="invalid(kind + '_directory')" class="field-error">{{ error?.message }}</p>
            </div>
            <div class="format-tags"><ElTag v-for="format in ['Word', 'Excel', 'Markdown']" :key="format" type="info" effect="plain">{{ format }}</ElTag><span>{{ t('timestamps') }}</span></div>
            <div v-if="model.picker" class="picker-wait" role="status"><span>{{ t('folderWaiting') }}</span><ElButton :disabled="!available.cancelDirectory" @click="actions.cancelDirectory">{{ model.picker.cancelling ? t('cancelling') : t('cancelWaiting') }}</ElButton></div>
          </ElCard>

          <ElCard id="auth_mode" shadow="never" header-class="section-heading" :class="{ 'needs-attention': invalid('auth_mode') }" tabindex="-1">
            <template #header><ElIcon class="section-icon" :size="20" aria-hidden="true"><Key /></ElIcon><h2>{{ t('connection') }}</h2></template>
            <div class="toggle-row">
              <div><label for="use-api-key">{{ t('useKey') }}</label><p>{{ t('consoleDefault') }}</p></div>
              <ElSwitch id="use-api-key" :model-value="form.useApiKey" :disabled="!available.changeAuth" :aria-label="t('useKey')" @update:model-value="actions.setAuthMode($event === true)" />
            </div>
            <div v-if="form.useApiKey" class="expanded-option">
              <KeyDisplay ref="keyDisplay" :status="model.auth.status" :disabled="!available.changeAuth" :t="t" @changed="actions.keyChanged" @save="saveApiKey" />
              <p class="helper">{{ t('keySaveHelp') }}</p>
            </div>
            <p v-if="invalid('auth_mode')" class="field-error">{{ error?.message }}</p>
          </ElCard>
        </ElForm>

      </div>
      <footer>{{ t('footer') }}<span>{{ t('brand') }}</span></footer>
    </main>

    <div v-if="model.session && !terminal && model.phase !== 'unavailable'" class="action-bar">
      <div class="action-inner">
        <div class="action-copy"><strong>{{ model.preview ? t('reviewTitle') : t('next') }}</strong><p>{{ model.preview ? t('reviewHelp') : t('nextHelp') }}</p></div>
        <div class="action-buttons">
          <ElButton v-if="model.preview" :icon="Edit" :loading="model.phase === 'returning'" :disabled="!available.edit" @click="actions.edit">{{ t('edit') }}</ElButton>
          <ElButton v-if="model.preview" type="primary" :icon="DocumentCopy" :disabled="!available.copy" @click="copyConfirmation">{{ t('copyToCodex') }}</ElButton>
          <ElButton v-else type="primary" :icon="View" :loading="model.phase === 'validating'" :disabled="!available.validate" @click="actions.validate">{{ t('check') }}</ElButton>
        </div>
      </div>
    </div>
  </ElConfigProvider>
</template>
