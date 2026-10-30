<script setup lang="ts">
import { ref } from 'vue';
import type { UploadCustomRequestOptions } from 'naive-ui';
import { downloadExcel } from '@/utils/excel';
import type { ExcelDownload } from '@/utils/excel';
import { $t } from '@/locales';

type Result<T> = Promise<{ data: T | null; error: unknown }>;

interface Props {
  importApi: (file: File) => Result<{ importedCount: number }>;
  exportApi: () => Result<ExcelDownload>;
  templateApi: () => Result<ExcelDownload>;
  canImport?: boolean;
  canExport?: boolean;
}

const props = withDefaults(defineProps<Props>(), { canImport: true, canExport: true });
const emit = defineEmits<{ imported: [] }>();
const busy = ref(false);

async function download(template = false) {
  if (busy.value) return;
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
  if (!file || busy.value) {
    options.onError();
    return;
  }
  if (!file.name.toLowerCase().endsWith('.xlsx') || file.size > 5 * 1024 * 1024) {
    window.$message?.error($t('common.excelFileLimit'));
    options.onError();
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
    <NButton v-if="canImport" size="small" :disabled="busy" @click="download(true)">
      {{ $t('common.excelTemplate') }}
    </NButton>
    <NUpload v-if="canImport" accept=".xlsx" :show-file-list="false" :custom-request="upload" :disabled="busy">
      <NButton size="small" :loading="busy" :disabled="busy">{{ $t('common.excelImport') }}</NButton>
    </NUpload>
    <NButton v-if="canExport" size="small" :loading="busy" :disabled="busy" @click="download(false)">
      {{ $t('common.excelExport') }}
    </NButton>
  </NSpace>
</template>
