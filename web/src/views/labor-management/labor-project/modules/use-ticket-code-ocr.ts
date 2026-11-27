import { onBeforeUnmount, ref } from 'vue';
import { fetchOcrRecognize } from '@/service/api';
import { $t } from '@/locales';

const SUPPORTED_IMAGE = /\.(jpe?g|png|gif|webp)$/i;
const MAX_IMAGE_BYTES = 10 * 1024 * 1024;

/**
 * Recognize ticket codes from a photo. Shared by the workbench create form so
 * dragging a ticket image and picking one behave identically.
 */
export function useTicketCodeOcr(applyCode: (code: string) => void) {
  const options = ref<{ label: string; value: string }[]>([]);
  const loading = ref(false);
  const dragging = ref(false);
  let session = 0;

  function isSupported(file: File | undefined): file is File {
    if (!file || !file.size || file.size > MAX_IMAGE_BYTES) return false;
    return (
      ['image/jpeg', 'image/png', 'image/gif', 'image/webp'].includes(file.type) || SUPPORTED_IMAGE.test(file.name)
    );
  }

  async function recognize(file: File | undefined) {
    if (!file || loading.value) return;
    if (!isSupported(file)) {
      window.$message?.warning($t('ocrTools.invalid', { size: 10 }));
      return;
    }
    const current = ++session;
    loading.value = true;
    options.value = [];
    try {
      const { data, error } = await fetchOcrRecognize(file, { useCls: true });
      if (current !== session) return;
      if (error || !data) {
        window.$message?.error($t('ocrTools.failed'));
        return;
      }
      options.value = [
        ...new Set(data.items.map(item => item.text.trim()).filter(value => value && value.length <= 100))
      ].map(value => ({ label: value, value }));
      if (options.value.length === 1) applyCode(options.value[0].value);
      if (!options.value.length) window.$message?.warning($t('page.labor_management.labor_work_hour.ocrEmpty'));
    } catch {
      if (current === session) window.$message?.error($t('ocrTools.failed'));
    } finally {
      if (current === session) loading.value = false;
    }
  }

  function handleChange(event: Event) {
    const input = event.target as HTMLInputElement;
    const [file] = Array.from(input.files ?? []);
    input.value = '';
    void recognize(file);
  }

  function handleDrop(event: DragEvent) {
    dragging.value = false;
    const transfer = event.dataTransfer;
    const files = Array.from(transfer?.files ?? []);
    const droppedItems = Array.from(transfer?.items ?? [])
      .map(item => (item.kind === 'file' ? item.getAsFile() : null))
      .filter((item): item is File => item !== null);
    const file = [...files, ...droppedItems].find(
      item => item.type.startsWith('image/') || SUPPORTED_IMAGE.test(item.name)
    );
    if (!file) {
      window.$message?.warning($t('ocrTools.dropUnavailable'));
      return;
    }
    void recognize(file);
  }

  /** Intercept screenshot paste but let ordinary text paste reach the input. */
  function handlePaste(event: ClipboardEvent) {
    const imageItem = Array.from(event.clipboardData?.items ?? []).find(
      item => item.kind === 'file' && item.type.startsWith('image/')
    );
    const file = imageItem?.getAsFile();
    if (!file) return;
    event.preventDefault();
    void recognize(file);
  }

  function reset() {
    session += 1;
    loading.value = false;
    options.value = [];
    dragging.value = false;
  }

  onBeforeUnmount(() => {
    session += 1;
  });

  return { options, loading, dragging, recognize, handleChange, handleDrop, handlePaste, reset };
}
