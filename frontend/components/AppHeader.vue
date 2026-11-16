<script setup lang="ts">
import { ElIcon, ElOption, ElSelect, ElText } from "element-plus";
import { Headset, Monitor, Moon, Sunny } from "@element-plus/icons-vue";
import type { Language, Theme } from "../types";
import type { Translate } from "../i18n";

defineProps<{ version: string | null | undefined; languageDisabled?: boolean; t: Translate }>();
const language = defineModel<Language>("language", { required: true });
const theme = defineModel<Theme>("theme", { required: true });
const emit = defineEmits<{ home: [] }>();
</script>

<template>
  <header class="topbar">
    <div class="topbar-inner">
      <a class="brand" href="#page-title" @click.prevent="emit('home')">
        <ElIcon class="brand-mark" :size="22" aria-hidden="true"><Headset /></ElIcon>
        <span class="brand-label"><span>MemoFlow</span><ElText v-if="version !== undefined" class="skill-version" type="info" size="small">{{ version ? `v${version}` : t('developmentBuild') }}</ElText></span>
      </a>
      <div class="appearance-controls">
        <ElSelect id="interface-language" v-model="language" :aria-label="t('language')" :disabled="languageDisabled" class="language-select">
          <ElOption value="zh-CN" label="简体中文" /><ElOption value="en" label="English" />
        </ElSelect>
        <ElSelect id="theme" v-model="theme" :aria-label="t('theme')" class="theme-select">
          <template #prefix><ElIcon :size="16" aria-hidden="true"><component :is="theme === 'system' ? Monitor : theme === 'light' ? Sunny : Moon" /></ElIcon></template>
          <ElOption value="system" :label="t('system')" /><ElOption value="light" :label="t('light')" /><ElOption value="dark" :label="t('dark')" />
        </ElSelect>
      </div>
    </div>
  </header>
</template>
