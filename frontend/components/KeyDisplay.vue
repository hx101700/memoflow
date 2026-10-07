<script setup lang="ts">
import { onBeforeUnmount, ref } from "vue";
import { ElButton, ElFormItem, ElInput } from "element-plus";
import type { Translate } from "../i18n";
import type { Model } from "../types";

defineProps<{ status: Model["auth"]["status"]; disabled: boolean; t: Translate }>();
// 凭据仅驻留在显示组件中，进入预览或关闭组件时清空。
const value = ref("");
const emit = defineEmits<{ changed: []; save: [] }>();

// 将已有 API Key 显示到密码输入框。
function setValue(key: string): void { value.value = key; }

// 在用户保存或检查时交付当前输入，供接口保存到本机环境文件。
function getValue(): string { return value.value; }

onBeforeUnmount(() => { value.value = ""; });
defineExpose({ setValue, getValue });
</script>

<template>
  <ElFormItem label="DASHSCOPE_API_KEY" for="api-key-value">
    <ElInput id="api-key-value" v-model="value" type="password" show-password
      autocomplete="off" :disabled="disabled || status === 'loading'" :placeholder="status === 'loading' ? t('loadingKey') : t('enterKey')" @input="emit('changed')">
      <template #append>
        <ElButton :loading="status === 'saving'" :disabled="disabled || !['dirty', 'failed'].includes(status) || !value.trim()" @click="emit('save')">{{ t('saveKey') }}</ElButton>
      </template>
    </ElInput>
  </ElFormItem>
</template>
