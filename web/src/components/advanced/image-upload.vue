<script setup lang="ts" generic="T extends string | string[] = string">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import type { UploadCustomRequestOptions, UploadFileInfo, UploadInst } from 'naive-ui';
import { fetchUploadImage, fetchUploadOptions } from '@/service/api/upload';
import type { ImageValue } from '@/utils/image';
import { imageSrc, imageUrls } from '@/utils/image';
import { $t } from '@/locales';

defineOptions({ name: 'ImageUpload' });
const props = withDefaults(
  defineProps<{
    value?: T | null;
    limit?: number;
    maxSizeMb?: number;
    disabled?: boolean;
    /** Array for JSON/list models; comma-separated string for CharField/TextField. */
    valueType?: 'string' | 'array';
  }>(),
  { value: undefined, limit: 5, maxSizeMb: undefined, disabled: false, valueType: 'string' }
);
const emit = defineEmits<{
  'update:value': [value: T];
  'update:busy': [busy: boolean];
}>();
const files = ref<UploadFileInfo[]>([]);
const uploadRef = ref<UploadInst | null>(null);
const serverMaxSize = ref(5);
const ready = ref(false);
const requests = new Map<string, AbortController>();
const stored = new Map<string, string>();
const sizeLimit = computed(() => Math.min(props.maxSizeMb ?? serverMaxSize.value, serverMaxSize.value));
const busy = ref(false);
let alive = true;
let dropSequence = 0;

function sync(value: ImageValue) {
  for (const controller of requests.values()) controller.abort();
  requests.clear();
  stored.clear();
  files.value = imageUrls(value).map((url, index) => {
    const id = `stored-${index}`;
    stored.set(id, url);
    return { id, name: url.split('/').pop() || 'image', status: 'finished', url: imageSrc(url) };
  });
  updateBusy();
}

function updateBusy() {
  busy.value = files.value.some(file => file.status === 'pending' || file.status === 'uploading');
  emit('update:busy', busy.value);
}

function publish() {
  const urls = files.value.flatMap(file => (stored.has(file.id) ? [stored.get(file.id)!] : []));
  if (JSON.stringify(urls) === JSON.stringify(imageUrls(props.value))) return;
  const next = props.valueType === 'array' || Array.isArray(props.value) ? urls : urls.join(',');
  emit('update:value', next as T);
}

function updateFiles(next: UploadFileInfo[]) {
  const ids = new Set(next.map(file => file.id));
  for (const [id, controller] of requests) {
    if (!ids.has(id)) {
      controller.abort();
      requests.delete(id);
    }
  }
  for (const id of stored.keys()) if (!ids.has(id)) stored.delete(id);
  files.value = next;
  updateBusy();
  publish();
}

function beforeUpload({ file }: { file: UploadFileInfo }) {
  const raw = file.file;
  if (!raw || !/\.(jpe?g|png|gif|webp)$/i.test(raw.name) || !raw.size || raw.size > sizeLimit.value * 1024 * 1024) {
    window.$message?.error($t('imageTools.invalid', { size: sizeLimit.value }));
    return false;
  }
  return true;
}

function exceed() {
  window.$message?.warning($t('imageTools.limit', { count: props.limit }));
}

async function dropImages(event: DragEvent) {
  if (props.disabled || !ready.value || !alive) return;
  const transfer = event.dataTransfer;
  let dropped = Array.from(transfer?.files ?? []);
  if (!dropped.length) {
    dropped = Array.from(transfer?.items ?? []).flatMap(item => {
      const file = item.kind === 'file' ? item.getAsFile() : null;
      return file ? [file] : [];
    });
  }
  if (!dropped.length) {
    window.$message?.warning($t('imageTools.dropUnavailable'));
    return;
  }
  const remaining = Math.max(0, props.limit - files.value.length);
  const accepted: UploadFileInfo[] = [];
  const extensions: Record<string, string> = {
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/gif': 'gif',
    'image/webp': 'webp'
  };
  for (const file of dropped) {
    // Chat apps can expose an image blob without a filename extension.
    const extension = extensions[file.type];
    const raw =
      !file.name.includes('.') && extension
        ? new File([file], `${file.name || 'image'}.${extension}`, { type: file.type, lastModified: file.lastModified })
        : file;
    const item: UploadFileInfo = {
      id: `drop-${++dropSequence}`,
      name: raw.name,
      file: raw,
      type: raw.type,
      status: 'pending'
    };
    if (beforeUpload({ file: item })) accepted.push(item);
  }
  if (accepted.length > remaining) exceed();
  const added = accepted.slice(0, remaining);
  if (!added.length) return;
  updateFiles([...files.value, ...added]);
  await nextTick();
  if (!alive) return;
  for (const item of added) uploadRef.value?.submit({ fileId: item.id });
}

function move(index: number, delta: number) {
  if (props.disabled || busy.value) return;
  const next = [...files.value];
  const target = index + delta;
  if (target < 0 || target >= next.length) return;
  [next[index], next[target]] = [next[target], next[index]];
  updateFiles(next);
}

async function upload(options: UploadCustomRequestOptions) {
  const raw = options.file.file;
  if (!raw) {
    options.onError();
    return;
  }
  const controller = new AbortController();
  requests.set(options.file.id, controller);
  updateBusy();
  try {
    const { data, error } = await fetchUploadImage(raw, controller.signal, percent => options.onProgress({ percent }));
    if (!alive || controller.signal.aborted || !files.value.some(file => file.id === options.file.id)) return;
    if (error || !data) {
      options.onError();
      return;
    }
    stored.set(options.file.id, data.url);
    options.file.url = imageSrc(data.url);
    options.onFinish();
    publish();
  } catch {
    if (alive && !controller.signal.aborted) options.onError();
  } finally {
    requests.delete(options.file.id);
    if (alive) updateBusy();
  }
}

watch(
  () => props.value,
  value => {
    const current = files.value.flatMap(file => (stored.has(file.id) ? [stored.get(file.id)!] : []));
    if (JSON.stringify(imageUrls(value)) !== JSON.stringify(current)) sync(value);
  },
  { deep: true, immediate: true }
);

onMounted(async () => {
  const { data, error } = await fetchUploadOptions();
  if (!alive) return;
  if (!error && data) {
    serverMaxSize.value = data.maxSizeMb;
    ready.value = true;
  }
});
onBeforeUnmount(() => {
  alive = false;
  for (const controller of requests.values()) controller.abort();
  emit('update:busy', false);
});
defineExpose({ busy });
</script>

<template>
  <div class="w-full" @dragover.prevent @drop.capture.prevent.stop="dropImages">
    <NUpload
      ref="uploadRef"
      :file-list="files"
      accept=".jpg,.jpeg,.png,.gif,.webp"
      list-type="image-card"
      :max="limit"
      :multiple="limit > 1"
      :disabled="disabled || !ready"
      :custom-request="upload"
      :should-use-thumbnail-url="() => true"
      @before-upload="beforeUpload"
      @update:file-list="updateFiles"
      @exceed="exceed"
    >
      {{ $t('imageTools.add') }}
    </NUpload>
    <p class="mt-2 rounded border border-dashed border-gray-300 p-3 text-sm text-gray-500">
      {{ $t('imageTools.dropHint') }}
    </p>
    <div v-if="files.length > 1 && !disabled" class="mt-2 flex flex-wrap gap-2">
      <NSpace v-for="(file, index) in files" :key="file.id" align="center" :size="4">
        <span class="text-xs">{{ index + 1 }}</span>
        <NButton
          size="tiny"
          :disabled="busy || index === 0"
          :aria-label="$t('imageTools.moveEarlier')"
          @click="move(index, -1)"
        >
          ←
        </NButton>
        <NButton
          size="tiny"
          :disabled="busy || index === files.length - 1"
          :aria-label="$t('imageTools.moveLater')"
          @click="move(index, 1)"
        >
          →
        </NButton>
      </NSpace>
    </div>
    <p class="mt-2 text-xs text-gray-500">{{ $t('imageTools.tip', { size: sizeLimit, count: limit }) }}</p>
  </div>
</template>
