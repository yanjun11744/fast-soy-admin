<script setup lang="ts">
import { computed, ref, shallowRef } from 'vue';
import type { UploadCustomRequestOptions } from 'naive-ui';
import { downloadExcel } from '@/utils/excel';
import type { ExcelDownload, ExcelImportApi, ExcelPreviewApi } from '@/utils/excel';
import { $t } from '@/locales';
import ExcelImportPreview from './excel-import-preview.vue';

type Result<T> = Promise<{ data: T | null; error: unknown }>;

interface Props {
  importApi: ExcelImportApi;
  previewApi?: ExcelPreviewApi;
  exportApi: (parentFields?: string[]) => Result<ExcelDownload>;
  exportSelectedApi?: (ids: string[], parentFields?: string[]) => Result<ExcelDownload>;
  exportParentFields?: { name: string; label: string }[];
  selectedIds?: string[];
  templateApi: () => Result<ExcelDownload>;
  canImport?: boolean;
  canExport?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  canImport: true,
  canExport: true,
  previewApi: undefined,
  exportSelectedApi: undefined,
  exportParentFields: () => [],
  selectedIds: () => []
});
const emit = defineEmits<{ imported: [] }>();
const busy = ref(false);
const selectedFile = shallowRef<File | null>(null);
const exportDialog = ref(false);
const selectedParentFields = ref<string[]>([]);
const pendingIds = ref<string[] | undefined>();
const exportOptions = computed(() => [
  { label: $t('common.excelExportFiltered'), key: 'filtered' },
  {
    label: $t('common.excelExportSelected', { count: props.selectedIds.length }),
    key: 'selected',
    disabled: props.selectedIds.length === 0
  }
]);

async function download(template = false, selected = false) {
  if (busy.value || selectedFile.value || exportDialog.value) return;
  if (template ? !props.canImport : !props.canExport) return;
  if (selected && (!props.exportSelectedApi || props.selectedIds.length === 0)) return;
  const ids = selected ? [...props.selectedIds] : undefined;
  if (!template && props.exportParentFields.length) {
    pendingIds.value = ids;
    selectedParentFields.value = props.exportParentFields.map(field => field.name);
    exportDialog.value = true;
    return;
  }
  await performDownload(template, ids);
}

async function confirmExport() {
  if (busy.value || !props.canExport) return;
  await performDownload(false, pendingIds.value, [...selectedParentFields.value]);
}

async function performDownload(template: boolean, ids?: string[], parentFields?: string[]) {
  if (busy.value) return;
  if (ids && (!ids.length || !props.exportSelectedApi)) return;
  busy.value = true;
  try {
    const result =
      ids && props.exportSelectedApi
        ? parentFields === undefined
          ? props.exportSelectedApi(ids)
          : props.exportSelectedApi(ids, parentFields)
        : template
          ? props.templateApi()
          : parentFields === undefined
            ? props.exportApi()
            : props.exportApi(parentFields);
    const { data, error } = await result;
    if (!error && data) {
      downloadExcel(data);
      exportDialog.value = false;
    }
  } finally {
    busy.value = false;
  }
}

async function upload(options: UploadCustomRequestOptions) {
  const file = options.file.file;
  if (!file || busy.value || selectedFile.value || exportDialog.value) {
    options.onError();
    return;
  }
  if (!file.name.toLowerCase().endsWith('.xlsx') || file.size > 5 * 1024 * 1024) {
    window.$message?.error($t('common.excelFileLimit'));
    options.onError();
    return;
  }
  if (props.previewApi) {
    selectedFile.value = file;
    options.onFinish();
    return;
  }
  busy.value = true;
  try {
    const { data, error } = await props.importApi(file);
    if (error || !data) {
      options.onError();
      return;
    }
    window.$message?.success(
      $t('common.excelImportSuccess', {
        created: data.createdCount ?? data.importedCount - (data.updatedCount ?? 0),
        updated: data.updatedCount ?? 0
      })
    );
    options.onFinish();
    emit('imported');
  } catch {
    options.onError();
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <NSpace align="center" wrap>
    <NButton v-if="canImport" size="small" :disabled="busy || Boolean(selectedFile)" @click="download(true)">
      {{ $t('common.excelTemplate') }}
    </NButton>
    <NUpload
      v-if="canImport"
      accept=".xlsx"
      :show-file-list="false"
      :custom-request="upload"
      :disabled="busy || Boolean(selectedFile)"
    >
      <NButton size="small" :loading="busy" :disabled="busy || Boolean(selectedFile)">
        {{ $t('common.excelImport') }}
      </NButton>
    </NUpload>
    <NDropdown
      v-if="canExport && exportSelectedApi"
      trigger="click"
      :options="exportOptions"
      :disabled="busy || Boolean(selectedFile)"
      @select="key => download(false, key === 'selected')"
    >
      <NButton size="small" :loading="busy" :disabled="busy || Boolean(selectedFile)">
        {{ $t('common.excelExport') }} ▾
      </NButton>
    </NDropdown>
    <NButton
      v-else-if="canExport"
      size="small"
      :loading="busy"
      :disabled="busy || Boolean(selectedFile)"
      @click="download(false)"
    >
      {{ $t('common.excelExport') }}
    </NButton>
    <ExcelImportPreview
      v-if="selectedFile && previewApi"
      :file="selectedFile"
      :preview-api="previewApi"
      :import-api="importApi"
      @close="selectedFile = null"
      @imported="emit('imported')"
    />
    <NModal
      v-if="exportDialog"
      v-model:show="exportDialog"
      preset="card"
      :title="$t('common.excelDetailExport')"
      class="w-140 max-w-95vw"
      :mask-closable="!busy"
      :close-on-esc="!busy"
      :closable="!busy"
    >
      <p class="mb-4">{{ $t('common.excelParentFieldsHint') }}</p>
      <NFormItem :label="$t('common.excelParentFields')">
        <NCheckboxGroup v-model:value="selectedParentFields" :disabled="busy">
          <NSpace wrap>
            <NCheckbox v-for="field in exportParentFields" :key="field.name" :value="field.name" :label="field.label" />
          </NSpace>
        </NCheckboxGroup>
      </NFormItem>
      <template #footer>
        <NSpace justify="end">
          <NButton :disabled="busy" @click="exportDialog = false">{{ $t('common.cancel') }}</NButton>
          <NButton type="primary" :loading="busy" :disabled="!canExport" @click="confirmExport">
            {{ $t('common.excelExport') }}
          </NButton>
        </NSpace>
      </template>
    </NModal>
  </NSpace>
</template>
