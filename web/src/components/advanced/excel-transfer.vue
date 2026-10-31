<script setup lang="ts">
import { ref, shallowRef } from 'vue';
import type { UploadCustomRequestOptions } from 'naive-ui';
import { downloadExcel } from '@/utils/excel';
import type { ExcelDownload, ExcelImportApi, ExcelPreviewApi } from '@/utils/excel';
import { $t } from '@/locales';
import ExcelImportPreview from './excel-import-preview.vue';

type Result<T> = Promise<{ data: T | null; error: unknown }>;

interface Props {
  importApi: ExcelImportApi;
  previewApi?: ExcelPreviewApi;
  exportApi: () => Result<ExcelDownload>;
  templateApi: () => Result<ExcelDownload>;
  canImport?: boolean;
  canExport?: boolean;
}

const props = withDefaults(defineProps<Props>(), { canImport: true, canExport: true, previewApi: undefined });
const emit = defineEmits<{ imported: [] }>();
const busy = ref(false);
const selectedFile = shallowRef<File | null>(null);

async function download(template = false) {
  if (busy.value || selectedFile.value) return;
  busy.value = true;
  try {
    const { data, error } = await (template ? props.templateApi() : props.exportApi());
    if (!error && data) downloadExcel(data);
  } finally {
    busy.value = false;
  }
}

async function upload(options: UploadCustomRequestOptions) {
  const file = options.file.file;
  if (!file || busy.value || selectedFile.value) {
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
    window.$message?.success($t('common.excelImportSuccess', { count: data.importedCount }));
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
    <NButton
      v-if="canExport"
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
  </NSpace>
</template>
