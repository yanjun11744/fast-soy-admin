<script setup lang="ts">
import { computed } from 'vue';
import type { ImageValue } from '@/utils/image';
import { imageSrc, imageUrls } from '@/utils/image';
import { $t } from '@/locales';

defineOptions({ name: 'ImagePreview' });
const props = withDefaults(defineProps<{ value?: ImageValue; width?: number; height?: number }>(), {
  value: '',
  width: 64,
  height: 64
});
const sources = computed(() => imageUrls(props.value).map(imageSrc).filter(Boolean));
</script>

<template>
  <NImageGroup>
    <NSpace v-if="sources.length" :size="8" align="center">
      <NImage
        v-for="(src, index) in sources"
        :key="`${index}-${src}`"
        :src="src"
        :width="width"
        :height="height"
        object-fit="cover"
        :alt="$t('imageTools.imageAlt', { index: index + 1 })"
        :img-props="{ loading: 'lazy' }"
        class="overflow-hidden rounded"
      />
    </NSpace>
    <span v-else class="text-gray-400">—</span>
  </NImageGroup>
</template>
