<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import ImageUpload from '@/components/advanced/image-upload.vue';
import { fetchUploadedImages, fetchUploadSettings, fetchUpdateUploadSettings } from '@/service/api/upload';
import type { UploadedImage } from '@/service/api/upload';
import { useAuth } from '@/hooks/business/auth';
import { imageSrc } from '@/utils/image';
import { $t } from '@/locales';

defineOptions({ name: 'UploadManage' });
const { hasAuth } = useAuth();
const settings = reactive({ storageRoot: '', maxSizeMb: 5 });
const settingsReady = ref(false);
const saving = ref(false);
const loading = ref(false);
const busy = ref(false);
const uploadValue = ref('');
const uploaderVersion = ref(0);
const records = ref<UploadedImage[]>([]);
const name = ref('');
const current = ref(1);
const total = ref(0);
let requestVersion = 0;

async function loadImages(page = current.value) {
  current.value = page;
  const version = ++requestVersion;
  loading.value = true;
  try {
    const { data, error } = await fetchUploadedImages({ current: page, size: 12, name: name.value });
    if (!error && data && version === requestVersion) {
      records.value = data.records;
      total.value = data.total;
    }
  } finally {
    if (version === requestVersion) loading.value = false;
  }
}

async function saveSettings() {
  if (saving.value || busy.value || !settings.storageRoot.trim()) return;
  saving.value = true;
  try {
    const { data, error } = await fetchUpdateUploadSettings(settings);
    if (!error && data) {
      Object.assign(settings, data);
      uploaderVersion.value += 1;
      window.$message?.success($t('common.updateSuccess'));
    }
  } finally {
    saving.value = false;
  }
}

async function copyUrl(url: string) {
  try {
    await navigator.clipboard.writeText(new URL(imageSrc(url), window.location.origin).href);
    window.$message?.success($t('imageTools.copied'));
  } catch {
    window.$message?.error($t('imageTools.copyFailed'));
  }
}

onMounted(async () => {
  await Promise.all([
    loadImages(),
    (async () => {
      const { data, error } = await fetchUploadSettings();
      if (!error && data) {
        Object.assign(settings, data);
        settingsReady.value = true;
      }
    })()
  ]);
});
</script>

<template>
  <NSpace vertical :size="16">
    <NCard :title="$t('imageTools.settings')" :bordered="false" class="card-wrapper">
      <NAlert type="info" class="mb-4">{{ $t('imageTools.directoryHint') }}</NAlert>
      <NForm label-placement="top" :disabled="!settingsReady || saving || !hasAuth('B_SYSTEM_UPLOAD_CONFIG')">
        <NFormItem :label="$t('imageTools.directory')">
          <NInput v-model:value="settings.storageRoot" :maxlength="1000" />
        </NFormItem>
        <NFormItem :label="$t('imageTools.maxSize')">
          <NInputNumber v-model:value="settings.maxSizeMb" :min="1" :max="20" :show-button="true" />
        </NFormItem>
        <NButton
          v-if="hasAuth('B_SYSTEM_UPLOAD_CONFIG')"
          type="primary"
          :loading="saving"
          :disabled="busy || !settingsReady"
          @click="saveSettings"
        >
          {{ $t('common.confirm') }}
        </NButton>
      </NForm>
    </NCard>
    <NCard
      v-if="hasAuth('B_SYSTEM_UPLOAD_CREATE')"
      :title="$t('imageTools.add')"
      :bordered="false"
      class="card-wrapper"
    >
      <ImageUpload
        :key="uploaderVersion"
        v-model:value="uploadValue"
        v-model:busy="busy"
        :limit="10"
        @update:value="() => loadImages(1)"
      />
    </NCard>
    <NCard :title="$t('imageTools.library')" :bordered="false" class="card-wrapper">
      <NSpace class="mb-4" align="center">
        <NInput v-model:value="name" :placeholder="$t('imageTools.search')" clearable @keyup.enter="loadImages(1)" />
        <NButton :loading="loading" @click="loadImages(1)">{{ $t('common.search') }}</NButton>
      </NSpace>
      <NSpin :show="loading">
        <NEmpty v-if="!records.length" :description="$t('imageTools.empty')" />
        <NImageGroup>
          <div v-if="records.length" class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            <NCard v-for="image in records" :key="image.key" size="small">
              <NImage
                :src="imageSrc(image.url)"
                :width="160"
                :height="120"
                object-fit="cover"
                :alt="image.name"
                :img-props="{ loading: 'lazy' }"
              />
              <NEllipsis class="mt-2 w-full">{{ image.name }}</NEllipsis>
              <p class="text-xs text-gray-500">
                {{ image.width }} × {{ image.height }} · {{ (image.size / 1024).toFixed(1) }} KB
              </p>
              <p class="mb-2 text-xs text-gray-500">{{ image.fmtCreatedAt }}</p>
              <NButton size="small" @click="copyUrl(image.url)">{{ $t('imageTools.copy') }}</NButton>
            </NCard>
          </div>
        </NImageGroup>
      </NSpin>
      <NPagination class="mt-4" :page="current" :page-size="12" :item-count="total" @update:page="loadImages" />
    </NCard>
  </NSpace>
</template>
