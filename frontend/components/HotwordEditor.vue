<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { ElAlert, ElButton, ElInput, ElPagination, ElTable, ElTableColumn, ElUpload } from "element-plus";
import type { UploadFile } from "element-plus";
import { Delete, Download, Plus, Upload } from "@element-plus/icons-vue";
import type { EditorRow, ErrorDetail, HotwordField, ImportState, Model } from "../types";
import type { Translate } from "../i18n";

const props = defineProps<{
  rows: EditorRow[]; validation: Model["hotwords"]; imported: ImportState;
  disabled: boolean; downloading: boolean; templateDisabled: boolean;
  message: string; limit: number; fileLimit: number; t: Translate;
}>();
const emit = defineEmits<{
  import: [files: readonly File[]]; download: []; add: []; remove: [key: number];
  change: [key: number, field: HotwordField, value: string];
}>();
const page = ref(1);
const pageSize = 50;
const pageRows = computed(() => props.rows.slice((page.value - 1) * pageSize, page.value * pageSize));
const rowIssues = computed(() => {
  const grouped = new Map<number, ErrorDetail[]>();
  for (const issue of props.validation.issues) {
    if (issue.row !== undefined && issue.field !== "header") grouped.set(issue.row, [...(grouped.get(issue.row) ?? []), issue]);
  }
  return grouped;
});
const generalIssues = computed(() => {
  const rows = new Set(props.rows.map(row => row.row));
  return props.validation.issues.filter(issue => issue.field === "header" || issue.row === undefined || !rows.has(issue.row));
});
const issueRows = computed(() => props.rows.filter(row => rowIssues.value.has(row.row)));
const issuePages = computed(() => new Set(props.rows.flatMap((row, index) =>
  rowIssues.value.has(row.row) ? [Math.floor(index / pageSize) + 1] : [])));

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
function cellIssues(row: number, field: HotwordField): ErrorDetail[] {
  return (rowIssues.value.get(row) ?? []).filter(issue => issue.field === field || field === "text" && issue.field !== "weight");
}

// 定位问题所在页与单元格，供检查结果和行号按钮复用。
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
  page.value = Math.floor(index / pageSize) + 1;
  await nextTick();
  const field = rowIssues.value.get(props.rows[index].row)?.[0]?.field === "weight" ? "weight" : "text";
  const input = document.getElementById(`hotword-${row}-${field}`);
  input?.focus({ preventScroll: true });
  input?.scrollIntoView({ block: "center" });
}

// 切换到当前页之后的首个问题行，并在末尾回到第一处。
function nextIssue(): void {
  const last = pageRows.value.at(-1)?.row ?? -1;
  void focusRow(issueRows.value.find(row => row.row > last)?.row ?? issueRows.value[0]?.row);
}

// 新增后显示新行，便于直接填写热词。
async function addRow(): Promise<void> {
  emit("add");
  await nextTick();
  await focusRow(props.rows.at(-1)?.row);
}

watch(() => props.rows.length, () => { page.value = Math.min(page.value, Math.max(1, Math.ceil(props.rows.length / pageSize))); });
defineExpose({ focusRow });
</script>

<template>
  <div class="hotword-editor">
    <div class="hotword-toolbar">
      <ElUpload :auto-upload="false" :show-file-list="false" :file-list="[]" :limit="1" accept=".xlsx"
        :disabled="disabled" :on-change="selected" :on-exceed="exceeded">
        <ElButton :icon="Upload" :disabled="disabled" :loading="imported.status === 'importing'">{{ t('importHotwords') }}</ElButton>
      </ElUpload>
      <ElButton :icon="Plus" :disabled="disabled" @click="addRow">{{ t('addHotword') }}</ElButton>
      <ElButton text :icon="Download" :disabled="templateDisabled" :loading="downloading" @click="emit('download')">{{ t('template') }}</ElButton>
    </div>
    <p class="helper">{{ t('hotwordHelp', { count: limit }) }} {{ t('hotwordLimit', { size: fileLimit }) }}</p>
    <p v-if="imported.name && imported.status === 'ready'" class="helper">{{ t('importedHotwords', { name: imported.name }) }}</p>
    <ElAlert v-if="message || validation.issues.length" id="hotword-issues" tabindex="-1" type="error" :closable="false" show-icon class="hotword-notice"
      :title="message || t('hotwordIssues', { count: validation.issues.length })">
      <p v-if="issueRows.length">{{ t('hotwordIssueHelp') }}</p>
      <ul v-if="generalIssues.length" class="error-details">
        <li v-for="(issue, index) in generalIssues" :key="index">
          <strong v-if="issue.row !== undefined">{{ t('row', { row: issue.row }) }} · </strong>{{ issue.message }}
        </li>
      </ul>
      <ElButton v-if="issueRows.length" link type="danger" @click="focusRow()">{{ t('firstIssue') }}</ElButton>
      <ElButton v-if="issuePages.size > 1" link type="danger" @click="nextIssue">{{ t('nextIssuePage') }}</ElButton>
    </ElAlert>
    <ElAlert v-for="warning in validation.warnings" :key="warning" :title="warning" type="warning" :closable="false" show-icon class="hotword-notice" />
    <ElTable :data="pageRows" row-key="key" :row-class-name="rowClassName" border max-height="520" class="hotword-table"
      :empty-text="t('hotwordEmpty')" :aria-label="t('hotwordFile')">
      <ElTableColumn prop="row" :label="t('rowNumber')" width="66" />
      <!-- @vue-generic {EditorRow} -->
      <ElTableColumn :label="t('textColumn')" min-width="190">
        <template #default="{ row }">
          <ElInput :id="`hotword-${row.row}-text`" :model-value="String(row.text ?? '')" :disabled="disabled"
            :aria-label="t('hotwordCell', { row: row.row })" :aria-invalid="cellIssues(row.row, 'text').length > 0"
            :aria-describedby="cellIssues(row.row, 'text').length ? `hotword-${row.row}-text-errors` : undefined"
            @update:model-value="emit('change', row.key, 'text', $event)" />
          <div v-if="cellIssues(row.row, 'text').length" :id="`hotword-${row.row}-text-errors`">
            <p v-for="(issue, index) in cellIssues(row.row, 'text')" :key="index" class="field-error">{{ issue.message }}</p>
          </div>
        </template>
      </ElTableColumn>
      <!-- @vue-generic {EditorRow} -->
      <ElTableColumn :label="t('weightColumn')" min-width="125">
        <template #default="{ row }">
          <ElInput :id="`hotword-${row.row}-weight`" :model-value="String(row.weight ?? '')" :disabled="disabled" inputmode="numeric"
            :aria-label="t('weightCell', { row: row.row })" :aria-invalid="cellIssues(row.row, 'weight').length > 0"
            :aria-describedby="cellIssues(row.row, 'weight').length ? `hotword-${row.row}-weight-errors` : undefined"
            @update:model-value="emit('change', row.key, 'weight', $event)" />
          <div v-if="cellIssues(row.row, 'weight').length" :id="`hotword-${row.row}-weight-errors`">
            <p v-for="(issue, index) in cellIssues(row.row, 'weight')" :key="index" class="field-error">{{ issue.message }}</p>
          </div>
        </template>
      </ElTableColumn>
      <!-- @vue-generic {EditorRow} -->
      <ElTableColumn width="80" :label="t('actions')" align="center">
        <template #default="{ row }">
          <ElButton text :icon="Delete" :disabled="disabled" :aria-label="t('removeHotword', { row: row.row })" @click="emit('remove', row.key)" />
        </template>
      </ElTableColumn>
    </ElTable>
    <div class="hotword-footer">
      <ElPagination v-if="rows.length > pageSize" v-model:current-page="page" :page-size="pageSize" :total="rows.length" layout="prev, pager, next" :pager-count="5" small />
      <span v-else class="helper">{{ t('hotwordRows', { count: rows.length }) }}</span>
    </div>
  </div>
</template>
