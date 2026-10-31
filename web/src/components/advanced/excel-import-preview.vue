<script setup lang="ts">
import { computed, onMounted, ref, shallowRef } from 'vue';
import type { ExcelImportApi, ExcelImportOptions, ExcelPreview, ExcelPreviewApi } from '@/utils/excel';
import { $t } from '@/locales';

interface Props {
  file: File;
  previewApi: ExcelPreviewApi;
  importApi: ExcelImportApi;
}

const props = defineProps<Props>();
const emit = defineEmits<{ close: []; imported: [] }>();
const busy = ref(false);
const preview = shallowRef<ExcelPreview | null>(null);
const sheet = ref<string | null>(null);
const headerRow = ref<number | null>(null);
// An empty string selects "ignore", including columns without an exact match.
const mapping = ref<string[]>([]);
const validated = ref('');
const sourceChanged = computed(
  () => sheet.value !== preview.value?.sheet || headerRow.value !== preview.value?.headerRow
);
const fieldOptions = computed(() => [
  { label: $t('common.excelIgnoreColumn'), value: '' },
  ...(preview.value?.fields.map(field => ({
    label: `${field.title} (${field.name})${field.required ? ' *' : ''}`,
    value: field.name
  })) ?? [])
]);

function selectSheet(value: string) {
  sheet.value = value;
  headerRow.value = null;
}

function selection(): ExcelImportOptions {
  return {
    sheet: sheet.value ?? undefined,
    headerRow: headerRow.value ?? undefined,
    columns: !sourceChanged.value && mapping.value.length ? mapping.value.map(value => value || null) : undefined
  };
}

const canImport = computed(() =>
  Boolean(preview.value?.rowCount && !preview.value.errors.length && validated.value === JSON.stringify(selection()))
);

async function validate() {
  if (busy.value) return;
  const submitted = selection();
  busy.value = true;
  validated.value = '';
  try {
    const { data, error } = await props.previewApi(props.file, submitted);
    if (error || !data) return;
    preview.value = data;
    sheet.value = data.sheet;
    headerRow.value = data.headerRow;
    mapping.value = data.columns.map(column => column.field ?? '');
    validated.value = JSON.stringify(selection());
  } finally {
    busy.value = false;
  }
}

async function importFile() {
  if (busy.value || !canImport.value) return;
  busy.value = true;
  try {
    const { data, error } = await props.importApi(props.file, selection());
    if (error || !data) return;
    window.$message?.success($t('common.excelImportSuccess', { count: data.importedCount }));
    emit('imported');
    emit('close');
  } finally {
    busy.value = false;
  }
}

onMounted(validate);
</script>

<template>
  <NModal
    :show="true"
    :mask-closable="false"
    :close-on-esc="!busy"
    @update:show="value => !value && !busy && emit('close')"
  >
    <NCard
      :title="$t('common.excelPreview')"
      :aria-label="$t('common.excelPreview')"
      class="max-w-900px w-95vw"
      role="dialog"
      aria-modal="true"
    >
      <NSpace vertical :size="16">
        <NAlert type="info" :show-icon="false">{{ $t('common.excelExactMatch') }}</NAlert>
        <NSpace align="center" wrap>
          <NFormItem :label="$t('common.excelSheet')" :show-feedback="false">
            <NSelect
              :value="sheet"
              class="w-220px"
              :options="preview?.sheets.map(name => ({ label: name, value: name })) ?? []"
              :disabled="busy"
              @update:value="selectSheet"
            />
          </NFormItem>
          <NFormItem :label="$t('common.excelHeaderRow')" :show-feedback="false">
            <NInputNumber v-model:value="headerRow" :min="1" :max="100" :precision="0" :disabled="busy" clearable />
          </NFormItem>
          <NButton :loading="busy" :disabled="busy" @click="validate">
            {{ $t('common.excelValidate') }}
          </NButton>
        </NSpace>
        <NSpin :show="busy">
          <div v-if="preview?.columns.length" class="max-h-400px overflow-auto">
            <NTable :single-line="false" size="small">
              <thead>
                <tr>
                  <th>{{ $t('common.excelSourceColumn') }}</th>
                  <th>{{ $t('common.excelTargetField') }}</th>
                  <th>{{ $t('common.excelSamples') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="column in preview.columns" :key="column.index">
                  <td>{{ column.index + 1 }}. {{ column.header }}</td>
                  <td class="min-w-240px">
                    <NSelect
                      v-model:value="mapping[column.index]"
                      :options="fieldOptions"
                      :disabled="busy || sourceChanged"
                      :placeholder="$t('common.excelSelectField')"
                      :aria-label="`${$t('common.excelTargetField')} ${column.index + 1}`"
                    />
                  </td>
                  <td class="max-w-260px break-all">{{ column.samples.join(' / ') }}</td>
                </tr>
              </tbody>
            </NTable>
          </div>
        </NSpin>
        <NAlert v-if="preview?.errors.length" type="warning">
          <div v-for="(error, index) in preview.errors" :key="index">{{ error }}</div>
        </NAlert>
        <div v-if="preview">{{ $t('common.excelRowCount', { count: preview.rowCount }) }}</div>
        <NSpace justify="end">
          <NButton :disabled="busy" @click="emit('close')">{{ $t('common.cancel') }}</NButton>
          <NButton type="primary" :loading="busy" :disabled="busy || !canImport" @click="importFile">
            {{ $t('common.excelConfirmImport') }}
          </NButton>
        </NSpace>
      </NSpace>
    </NCard>
  </NModal>
</template>
