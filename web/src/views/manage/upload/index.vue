<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import ImageUpload from '@/components/advanced/image-upload.vue';
import { fetchUploadSettings, fetchUpdateUploadSettings } from '@/service/api/upload';
import { useAuth } from '@/hooks/business/auth';
import { $t } from '@/locales';
import ImageLibrary from './modules/image-library.vue';

defineOptions({ name: 'UploadManage' });
const { hasAuth } = useAuth();
const settings = reactive({ storageRoot: '', maxSizeMb: 5 });
const settingsReady = ref(false);
const saving = ref(false);
const busy = ref(false);
const uploadVisible = ref(false);
const uploadValue = ref('');
const library = ref<InstanceType<typeof ImageLibrary>>();

async function saveSettings() {
  if (saving.value || busy.value || !settings.storageRoot.trim()) return;
  saving.value = true;
  try {
    const { data, error } = await fetchUpdateUploadSettings(settings);
    if (!error && data) {
      Object.assign(settings, data);
      window.$message?.success($t('common.updateSuccess'));
    }
  } finally { saving.value = false; }
}

function openUpload() {
  uploadValue.value = '';
  uploadVisible.value = true;
}

onMounted(async () => {
  const { data, error } = await fetchUploadSettings();
  if (!error && data) { Object.assign(settings, data); settingsReady.value = true; }
});
</script>

<template>
  <NSpace vertical :size="16">
    <NCollapse>
      <NCollapseItem :title="$t('imageTools.settings')" name="settings">
        <NCard :bordered="false" class="card-wrapper">
          <NAlert type="info" class="mb-4">{{ $t('imageTools.directoryHint') }}</NAlert>
          <NForm label-placement="top" :disabled="!settingsReady || saving || !hasAuth('B_SYSTEM_UPLOAD_CONFIG')">
            <NFormItem :label="$t('imageTools.directory')"><NInput v-model:value="settings.storageRoot" :maxlength="1000" /></NFormItem>
            <NFormItem :label="$t('imageTools.maxSize')"><NInputNumber v-model:value="settings.maxSizeMb" :min="1" :max="20" /></NFormItem>
            <NButton v-if="hasAuth('B_SYSTEM_UPLOAD_CONFIG')" type="primary" :loading="saving" :disabled="busy || !settingsReady" @click="saveSettings">{{ $t('common.confirm') }}</NButton>
          </NForm>
        </NCard>
      </NCollapseItem>
    </NCollapse>
    <ImageLibrary ref="library" @add="openUpload" />
    <NModal v-model:show="uploadVisible" preset="card" :title="$t('imageTools.add')" class="w-160 max-w-95vw">
      <ImageUpload v-if="uploadVisible" v-model:value="uploadValue" v-model:busy="busy" :limit="10" @update:value="() => library?.refresh()" />
    </NModal>
  </NSpace>
</template>
