<script setup lang="ts">
import { computed, nextTick } from "vue";
import { ElAlert, ElButton, ElInput, ElTable, ElTableColumn, ElUpload } from "element-plus";
import type { UploadFile } from "element-plus";
import { Delete, DocumentAdd, Download, Plus } from "@element-plus/icons-vue";
import type { EditorIssue, EditorRow, HotwordField, ImportState, Language, Model } from "../types";
import { localize, type Translate } from "../i18n";

const props = defineProps<{
  rows: EditorRow[]; validation: Model["hotwords"]; imported: ImportState;
  disabled: boolean; downloading: boolean; templateDisabled: boolean;
  message: string; limit: number; fileLimit: number; language: Language; t: Translate;
}>();
const emit = defineEmits<{
  import: [files: readonly File[]]; download: []; add: []; remove: [key: number];
  change: [key: number, field: HotwordField, value: string];
}>();
const rowIssues = computed(() => {
  const grouped = new Map<number, EditorIssue[]>();
  const numbers = new Map(props.rows.map(row => [row.key, row.row]));
  for (const issue of props.validation.issues) {
    const number = issue.key === undefined ? undefined : numbers.get(issue.key);
    if (number !== undefined) grouped.set(number, [...(grouped.get(number) ?? []), issue]);
  }
  return grouped;
});
const generalIssues = computed(() => {
  return props.validation.issues.filter(issue => issue.key === undefined);
});
const issueRows = computed(() => props.rows.filter(row => rowIssues.value.has(row.row)));

// 传递单个Excel文件，解析和规则检查由本机服务完成。
function selected(file: UploadFile): void {
  if (file.raw) emit("import", [file.raw]);
}

// 将多文件选择交给统一规则返回可见提示。
function exceeded(files: File[]): void { emit("import", files); }

// 使用公开行样式入口标红包含问题的词条。
function rowClassName({ row }: { row: EditorRow }): string {
  return rowIssues.value.has(row.row) ? "hotword-error-row" : "";
}

// 返回当前序号对应单元格的问题说明。
function cellIssues(row: number, field: HotwordField): EditorIssue[] {
  return (rowIssues.value.get(row) ?? []).filter(issue => issue.field === field || field === "text" && issue.field !== "weight");
}

// 滚动到出错单元格或表格级提示，并提供输入焦点。
async function focusRow(rowNumber?: number): Promise<void> {
  if (rowNumber === undefined && (generalIssues.value.length || props.message && !issueRows.value.length)) {
    const notice = document.getElementById("hotword-issues");
    notice?.focus({ preventScroll: true });
    notice?.scrollIntoView({ block: "center" });
    return;
  }
  const row = rowNumber ?? issueRows.value[0]?.row ?? props.rows[0]?.row;
  const index = props.rows.findIndex(entry => entry.row === row);
  if (index < 0) return;
  await nextTick();
  const field = rowIssues.value.get(props.rows[index].row)?.[0]?.field === "weight" ? "weight" : "text";
  const input = document.getElementById(`hotword-${row}-${field}`);
  input?.focus({ preventScroll: true });
  input?.scrollIntoView({ block: "center" });
}

// 新增后显示新行，便于直接填写热词。
async function addRow(): Promise<void> {
  emit("add");
  await nextTick();
  await focusRow(props.rows.at(-1)?.row);
}

defineExpose({ focusRow });
</script>

<template>
  <div class="hotword-editor">
    <div class="hotword-toolbar">
      <ElUpload :auto-upload="false" :show-file-list="false" :file-list="[]" :limit="1" accept=".xlsx"
        :disabled="disabled" :on-change="selected" :on-exceed="exceeded">
        <ElButton text :icon="DocumentAdd" :disabled="disabled" :loading="imported.status === 'importing'">{{ t('importHotwords') }}</ElButton>
      </ElUpload>
      <ElButton text :icon="Download" :disabled="templateDisabled" :loading="downloading" @click="emit('download')">{{ t('template') }}</ElButton>
    </div>
    <p class="helper">{{ t('hotwordHelp', { count: limit }) }} {{ t('hotwordLimit', { size: fileLimit }) }}</p>
    <p v-if="imported.name && imported.status === 'ready'" class="helper">{{ t('importedHotwords', { name: imported.name }) }}</p>
    <ElAlert v-if="message || validation.issues.length" id="hotword-issues" tabindex="-1" type="error" :closable="false" show-icon class="hotword-notice"
      :title="message || t('hotwordIssues')">
      <ul v-if="generalIssues.length" class="error-details">
        <li v-for="(issue, index) in generalIssues" :key="index">
          {{ localize(issue.message, language) }}
        </li>
      </ul>
    </ElAlert>
    <ElAlert v-for="(warning, index) in validation.warnings" :key="index" :title="localize(warning, language)" type="warning" :closable="false" show-icon class="hotword-notice" />
    <ElTable :data="rows" row-key="key" :row-class-name="rowClassName" :header-cell-style="{ fontWeight: '600' }" border max-height="420" class="hotword-table"
      :empty-text="t('hotwordEmpty')" :aria-label="t('hotwordFile')">
      <ElTableColumn prop="row" :label="t('rowNumber')" width="66" align="center" />
      <!-- @vue-generic {EditorRow} -->
      <ElTableColumn :label="t('textColumn')" min-width="190" header-align="center">
        <template #default="{ row }">
          <ElInput :id="`hotword-${row.row}-text`" :model-value="String(row.text ?? '')" :disabled="disabled"
            :aria-label="t('hotwordCell', { row: row.row })" :aria-invalid="cellIssues(row.row, 'text').length > 0"
            :aria-describedby="cellIssues(row.row, 'text').length ? `hotword-${row.row}-text-errors` : undefined"
            @update:model-value="emit('change', row.key, 'text', $event)" />
          <div v-if="cellIssues(row.row, 'text').length" :id="`hotword-${row.row}-text-errors`">
            <p v-for="(issue, index) in cellIssues(row.row, 'text')" :key="index" class="field-error">{{ localize(issue.message, language) }}</p>
          </div>
        </template>
      </ElTableColumn>
      <!-- @vue-generic {EditorRow} -->
      <ElTableColumn :label="t('weightColumn')" min-width="125" header-align="center">
        <template #default="{ row }">
          <ElInput :id="`hotword-${row.row}-weight`" :model-value="String(row.weight ?? '')" :disabled="disabled" inputmode="numeric" :input-style="{ textAlign: 'center' }"
            :aria-label="t('weightCell', { row: row.row })" :aria-invalid="cellIssues(row.row, 'weight').length > 0"
            :aria-describedby="cellIssues(row.row, 'weight').length ? `hotword-${row.row}-weight-errors` : undefined"
            @update:model-value="emit('change', row.key, 'weight', $event)" />
          <div v-if="cellIssues(row.row, 'weight').length" :id="`hotword-${row.row}-weight-errors`">
            <p v-for="(issue, index) in cellIssues(row.row, 'weight')" :key="index" class="field-error">{{ localize(issue.message, language) }}</p>
          </div>
        </template>
      </ElTableColumn>
      <template #append><ElButton text class="add-hotword-row" :icon="Plus" :disabled="disabled" @click="addRow">{{ t('addHotword') }}</ElButton></template>
      <!-- @vue-generic {EditorRow} -->
      <ElTableColumn width="80" :label="t('actions')" align="center">
        <template #default="{ row }">
          <ElButton text :icon="Delete" :disabled="disabled" :aria-label="t('removeHotword', { row: row.row })" @click="emit('remove', row.key)" />
        </template>
      </ElTableColumn>
    </ElTable>
    <div class="hotword-footer">
      <span class="helper">{{ t('hotwordRows', { count: rows.length }) }}</span>
    </div>
  </div>
</template>
