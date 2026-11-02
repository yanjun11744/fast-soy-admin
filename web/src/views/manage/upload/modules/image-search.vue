<script setup lang="ts">
import { toRaw } from 'vue';
import { jsonClone } from '@sa/utils';
import type { ImageSearch as ImageSearchParams } from '@/service/api/upload';
import { $t } from '@/locales';

defineOptions({ name: 'ImageSearch' });

const emit = defineEmits<{ search: [] }>();
const model = defineModel<ImageSearchParams>('model', { required: true });
const timeRange = defineModel<[string, string] | null>('timeRange', { required: true });

const defaultModel = jsonClone(toRaw(model.value));
const formatOptions = ['jpeg', 'png', 'gif', 'webp'].map(type => ({
  label: type.toUpperCase(),
  value: `image/${type}`
}));

function reset() {
  Object.assign(model.value, defaultModel);
  timeRange.value = null;
}

function search() {
  emit('search');
}
</script>

<template>
  <NCard :bordered="false" size="small" class="card-wrapper">
    <NCollapse>
      <NCollapseItem :title="$t('common.search')" name="image-search">
        <NForm :model="model" label-placement="left" :label-width="80">
          <NGrid responsive="screen" item-responsive>
            <NFormItemGi span="24 s:12 m:8" :label="$t('imageTools.name')" path="name" class="pr-24px">
              <NInput
                v-model:value="model.name"
                :placeholder="$t('imageTools.search')"
                clearable
                @keyup.enter="search"
              />
            </NFormItemGi>
            <NFormItemGi span="24 s:12 m:4" :label="$t('imageTools.format')" path="mediaType" class="pr-24px">
              <NSelect
                v-model:value="model.mediaType"
                :options="formatOptions"
                :placeholder="$t('imageTools.format')"
                clearable
              />
            </NFormItemGi>
            <NFormItemGi span="24 m:6" :label="$t('imageTools.uploadTime')" class="pr-24px">
              <NDatePicker
                v-model:formatted-value="timeRange"
                type="datetimerange"
                value-format="yyyy-MM-dd HH:mm:ss"
                clearable
                class="w-full"
              />
            </NFormItemGi>
            <NFormItemGi span="24 m:6" class="pr-24px" justify="end">
              <NSpace class="w-full" justify="end">
                <NButton @click="reset">
                  <template #icon>
                    <icon-ic-round-refresh class="text-icon" />
                  </template>
                  {{ $t('common.reset') }}
                </NButton>
                <NButton type="primary" ghost @click="search">
                  <template #icon>
                    <icon-ic-round-search class="text-icon" />
                  </template>
                  {{ $t('common.search') }}
                </NButton>
              </NSpace>
            </NFormItemGi>
          </NGrid>
        </NForm>
      </NCollapseItem>
    </NCollapse>
  </NCard>
</template>
