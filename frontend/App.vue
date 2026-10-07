<script setup lang="ts">
import { computed, h, nextTick, onMounted, onUnmounted, ref } from "vue";
import { ElAlert, ElButton, ElCard, ElConfigProvider, ElDescriptions, ElDescriptionsItem, ElDivider, ElForm, ElFormItem, ElIcon, ElInput, ElLink, ElMessage, ElOption, ElResult, ElSelect, ElStep, ElSteps, ElSwitch } from "element-plus";
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
import AudioField from "./components/AudioField.vue";
import HotwordEditor from "./components/HotwordEditor.vue";
import SettingsSummary from "./components/SettingsSummary.vue";

const props = defineProps<{ connect: (language: () => Language, t: Translate) => Api }>();
const { language, theme, t } = usePreferences();
const keyDisplay = ref<InstanceType<typeof KeyDisplay>>();
const hotwordEditor = ref<InstanceType<typeof HotwordEditor>>();

// 在控件完成渲染后定位错误字段或当前操作区域。
async function focus(target: string): Promise<void> {
  await nextTick();
  const region = document.getElementById(target) ?? document.getElementById("error-panel");
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
const configuring = computed(() => ["editing", "validating"].includes(model.phase));
const step = computed(() => model.preview ? 1 : 0);
const confirmationText = computed(() => t("confirmationMessage", { id: model.session?.session_id ?? "" }));
const contextLength = computed(() => Array.from(form.context).length);
const errorText = computed(() => error.value?.describe(language.value) ?? "");
const outputKinds: DirectoryKind[] = ["json", "document"];
// 中文和英文官方页面使用各自的章节锚点。
const enhancementRules = computed(() => language.value === "en" ? {
  hotwords: "https://www.alibabacloud.com/help/en/model-studio/improve-asr-accuracy#hotword-format-2",
  context: "https://www.alibabacloud.com/help/en/model-studio/improve-asr-accuracy#context-enhancement",
} : {
  hotwords: "https://help.aliyun.com/zh/model-studio/improve-asr-accuracy#hw_instant_fmt_h4",
  context: "https://help.aliyun.com/zh/model-studio/improve-asr-accuracy#ctx_enhance_h2",
});

// 单独保存 API Key 成功后显示本机保存回执。
async function saveApiKey(): Promise<void> {
  if (await actions.saveApiKey()) ElMessage.success({ message: () => h("span", t("keySaved")) });
}

// 复制带当前编辑会话编号的确认消息，供用户在 Codex 中发起交接。
async function copyConfirmation(): Promise<void> {
  if (!available.value.copy) return;
  try {
    await navigator.clipboard.writeText(confirmationText.value);
    ElMessage.success({ message: () => h("span", t("copied")) });
  } catch { ElMessage.error({ message: () => h("span", t("copyFailed")) }); }
}

// 判断当前错误是否属于指定输入区域。
function invalid(field: string): boolean {
  return error.value?.field === field;
}

// 读取输入位置的错误说明，供 Element Plus 表单关联。
function fieldMessage(field: string): string {
  return invalid(field) ? errorText.value : "";
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
          <ElSelect id="interface-language" v-model="language" :aria-label="t('language')" :disabled="!available.changeLanguage" class="language-select">
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
      <div class="workspace" :class="{ 'with-summary': model.session && configuring }">
        <div class="main-column">
          <div class="intro">
            <div>
              <h1 id="page-title" tabindex="-1">{{ t('title') }}</h1>
              <p>{{ model.phase === 'handed_off' ? t('endedLocal') : t('intro') }}</p>
            </div>
          </div>

          <ElSteps v-if="!terminal && model.phase !== 'unavailable'" :active="step" finish-status="success" class="steps" align-center>
            <ElStep :title="t('stepConfigure')" /><ElStep :title="t('stepReview')" />
          </ElSteps>
          <ElAlert v-if="configuring" :title="t('beforeStart')" type="info" :closable="false" show-icon class="intro-note" />
          <ElAlert v-if="error && model.phase !== 'unavailable' && !['audio_id', 'hotword_rows', 'context'].includes(error.field ?? '')" id="error-panel" tabindex="-1" class="page-notice" :title="errorText" type="error" :closable="false" show-icon />
          <p v-if="model.phase === 'loading'" class="loading-note" role="status">{{ t('loading') }}</p>
          <ElCard v-if="model.phase === 'unavailable'" id="session-unavailable" class="receipt" shadow="never" tabindex="-1">
            <ElResult icon="error" :title="t('unavailable')" :sub-title="errorText || t('unavailableHelp')" />
          </ElCard>
          <ElCard v-else-if="terminal" id="session-ended" class="receipt" shadow="never" tabindex="-1">
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

          <ElForm v-else-if="model.session && configuring" id="config-fields" :disabled="!available.editable" label-position="top" inline-message class="form-column" tabindex="-1" @submit.prevent="actions.validate">
            <ElCard id="audio_id" shadow="never" header-class="section-heading" :class="{ 'needs-attention': invalid('audio_id') }" tabindex="-1">
              <template #header><ElIcon class="section-icon" :size="20" aria-hidden="true"><Headset /></ElIcon><h2>{{ t('audioHeading') }}</h2><span class="section-aside">{{ t('oneFile') }}</span></template>
              <AudioField v-if="model.session" :audio="model.audio" :disabled="!available.selectAudio" :selecting="model.picker?.kind === 'audio'" :t="t"
                :requirements="t('audioLimits', { hours: model.session.limits.audio_seconds / 3600,
                  upload: model.session.limits.upload_bytes / 1_000_000_000 })"
                :supported-formats="t('audioFormats', { formats: model.session.audio_suffixes.map(s => s.slice(1).toUpperCase()).join(', ') })" @select="actions.selectAudio" />
              <p v-if="invalid('audio_id')" class="field-error">{{ errorText }}</p>
              <div v-if="model.picker?.kind === 'audio'" class="picker-wait" role="status"><span>{{ t('audioWaiting') }}</span><ElButton :disabled="!available.cancelPicker" @click="actions.cancelPicker">{{ model.picker.cancelling ? t('cancelling') : t('cancelWaiting') }}</ElButton></div>
            </ElCard>

            <ElCard id="settings" shadow="never" header-class="section-heading" tabindex="-1">
              <template #header><ElIcon class="section-icon" :size="20" aria-hidden="true"><Setting /></ElIcon><h2>{{ t('settings') }}</h2></template>
              <div id="language_hint" :class="{ 'needs-attention': invalid('language_hint') }" tabindex="-1">
                <ElFormItem :label="t('audioLanguage')" for="audio-language" :error="fieldMessage('language_hint')">
                  <ElSelect id="audio-language" v-model="form.language" :empty-values="[null, undefined]" filterable @change="actions.changed('language_hint')">
                    <ElOption value="" :label="t('automatic')" /><ElOption v-for="code in model.session.languages" :key="code" :value="code" :label="languageName(code, language)" />
                  </ElSelect>
                </ElFormItem>
              </div>
              <div class="toggle-row">
                <div><label for="diarization">{{ t('diarization') }}</label><p>{{ t('diarizationHelp') }} <span v-if="form.diarizationEnabled">{{ t('monoHelp') }}</span></p></div>
                <ElSwitch id="diarization" v-model="form.diarizationEnabled" :aria-label="t('diarization')" @change="actions.changed('speaker_count')" />
              </div>
              <div v-if="form.diarizationEnabled" class="expanded-option">
                <div id="speaker_count" :class="{ 'needs-attention': invalid('speaker_count') }" tabindex="-1">
                  <ElFormItem :label="t('speakers') + ' · ' + t('optional')" for="speaker-count" :error="fieldMessage('speaker_count')">
                    <ElInput id="speaker-count" v-model="form.speaker" inputmode="numeric" :placeholder="t('automatic')" @input="actions.changed('speaker_count')" />
                  </ElFormItem>
                  <p class="helper">{{ t('speakerHint', { min: model.session.limits.speaker_min, max: model.session.limits.speaker_max }) }}</p>
                </div>
              </div>
            </ElCard>

            <ElCard id="enhancement" shadow="never" header-class="section-heading enhancement-heading" tabindex="-1">
              <template #header><ElIcon class="section-icon" :size="20" aria-hidden="true"><Aim /></ElIcon><h2>{{ t('enhancement') }}</h2></template>
              <div class="enhancement-option">
                <div class="toggle-row">
                  <div class="enhancement-label"><label for="hotwords-enabled"><ElIcon :size="16" aria-hidden="true"><Reading /></ElIcon>{{ t('hotwords') }}</label><p>{{ t('hotwordsHelp') }}<ElLink type="primary" class="rules-link" :href="enhancementRules.hotwords" target="_blank" rel="noopener noreferrer">{{ t('hotwordRules') }}</ElLink></p></div>
                  <ElSwitch id="hotwords-enabled" :model-value="form.hotwordsEnabled" :disabled="!available.editHotwords" :aria-label="t('hotwords')" @update:model-value="actions.setHotwordsEnabled($event === true)" />
                </div>
                <div v-if="form.hotwordsEnabled" id="hotword_rows" class="expanded-option" :class="{ 'needs-attention': invalid('hotword_rows') }" tabindex="-1">
                  <HotwordEditor v-if="model.session" ref="hotwordEditor" :rows="form.hotwordRows" :validation="model.hotwords" :imported="model.hotwordImport"
                    :disabled="!available.editHotwords" :template-disabled="!available.template" :downloading="model.downloadingTemplate"
                    :message="fieldMessage('hotword_rows')" :limit="model.session.limits.hotwords_count"
                    :file-limit="model.session.limits.hotwords_bytes / 1_000_000" :language="language" :t="t"
                    @import="actions.importHotwords" @download="actions.downloadTemplate" @add="actions.addHotword"
                    @remove="actions.removeHotword" @change="actions.changeHotword" />
                </div>
              </div>
              <ElDivider />
              <div class="enhancement-option">
                <div class="toggle-row">
                  <div class="enhancement-label"><label for="context-enabled"><ElIcon :size="16" aria-hidden="true"><ChatLineSquare /></ElIcon>{{ t('context') }}</label><p>{{ t('contextHelp') }}<ElLink type="primary" class="rules-link" :href="enhancementRules.context" target="_blank" rel="noopener noreferrer">{{ t('contextRules') }}</ElLink></p></div>
                  <ElSwitch id="context-enabled" :model-value="form.contextEnabled" :aria-label="t('context')" @update:model-value="actions.setContextEnabled($event === true)" />
                </div>
                <div v-if="form.contextEnabled" id="context" class="expanded-option" :class="{ 'needs-attention': invalid('context') }" tabindex="-1">
                  <ElFormItem :error="fieldMessage('context')">
                    <ElInput id="context-text" v-model="form.context" type="textarea" :aria-label="t('reference')" :autosize="{ minRows: 4, maxRows: 10 }" :placeholder="t('contextPlaceholder')" @input="actions.changed('context')" />
                  </ElFormItem>
                  <div v-if="model.session" class="textarea-footer"><p class="helper">{{ t('contextHint', { count: model.session.limits.context_chars }) }}</p><span>{{ contextLength }} / {{ model.session.limits.context_chars }}</span></div>
                </div>
              </div>
            </ElCard>

            <ElCard id="outputs" shadow="never" header-class="section-heading" tabindex="-1">
              <template #header><ElIcon class="section-icon" :size="20" aria-hidden="true"><FolderOpened /></ElIcon><h2>{{ t('savingLocations') }}</h2></template>
              <div v-for="kind in outputKinds" :id="kind + '_directory'" :key="kind" class="output-field" :class="{ 'needs-attention': invalid(kind + '_directory') }" tabindex="-1">
                <div class="label-action"><label :for="kind + '-folder'">{{ t(kind === 'json' ? 'rawResult' : 'documents') }}</label>
                  <ElButton v-if="model.directories[kind] !== 'default'" text :disabled="!available.chooseDirectory" @click="actions.resetDirectory(kind)">{{ t('resetFolder') }}</ElButton></div>
                <div class="directory-row"><ElInput :id="kind + '-folder'" :model-value="model.directories[kind] === 'default' ? '' : model.directories[kind]" :placeholder="model.session?.output_defaults[kind]" :title="model.directories[kind] === 'default' ? model.session?.output_defaults[kind] : model.directories[kind]" readonly />
                  <ElButton :icon="FolderOpened" :disabled="!available.chooseDirectory" @click="actions.selectDirectory(kind)">{{ model.picker?.kind === kind ? t('choosingFolder') : t('chooseFolder') }}</ElButton></div>
                <p v-if="invalid(kind + '_directory')" class="field-error">{{ errorText }}</p>
              </div>
              <div v-if="model.picker && model.picker.kind !== 'audio'" class="picker-wait" role="status"><span>{{ t('folderWaiting') }}</span><ElButton :disabled="!available.cancelPicker" @click="actions.cancelPicker">{{ model.picker.cancelling ? t('cancelling') : t('cancelWaiting') }}</ElButton></div>
            </ElCard>

            <ElCard id="auth_mode" shadow="never" header-class="section-heading" :class="{ 'needs-attention': invalid('auth_mode') }" tabindex="-1">
              <template #header><ElIcon class="section-icon" :size="20" aria-hidden="true"><Key /></ElIcon><h2>{{ t('connection') }}</h2></template>
              <div class="toggle-row">
                <div><label for="use-api-key">{{ t('useKey') }}</label><p>{{ t(form.useApiKey ? 'keyModeHelp' : 'consoleDefault') }}</p></div>
                <ElSwitch id="use-api-key" :model-value="form.useApiKey" :disabled="!available.changeAuth" :aria-label="t('useKey')" @update:model-value="actions.setAuthMode($event === true)" />
              </div>
              <div v-if="form.useApiKey" class="expanded-option">
                <KeyDisplay ref="keyDisplay" :status="model.auth.status" :disabled="!available.changeAuth" :t="t" @changed="actions.keyChanged" @save="saveApiKey" />
                <p class="helper">{{ t('keySaveHelp') }}</p>
              </div>
              <p v-if="invalid('auth_mode')" class="field-error">{{ errorText }}</p>
            </ElCard>
          </ElForm>
        </div>
        <SettingsSummary v-if="model.session && configuring" :audio="model.audio" :form="form" :context-length="contextLength" :language="language" :t="t" />
      </div>
      <footer>{{ t('footer') }} · {{ t('provider') }}</footer>
    </main>

    <div v-if="model.session && !terminal && model.phase !== 'unavailable'" class="action-bar">
      <div class="action-inner">
        <div class="action-copy"><strong>{{ model.preview ? t('reviewTitle') : t('next') }}</strong><p v-if="!model.preview">{{ t('nextHelp') }}</p></div>
        <div class="action-buttons">
          <ElButton v-if="model.preview" :icon="Edit" :loading="model.phase === 'returning'" :disabled="!available.edit" @click="actions.edit">{{ t('edit') }}</ElButton>
          <ElButton v-if="model.preview" type="primary" :icon="DocumentCopy" :disabled="!available.copy" @click="copyConfirmation">{{ t('copyToCodex') }}</ElButton>
          <ElButton v-else type="primary" :icon="View" :loading="model.phase === 'validating'" :disabled="!available.validate" @click="actions.validate">{{ t('check') }}</ElButton>
        </div>
      </div>
    </div>
  </ElConfigProvider>
</template>
