import { defineComponent } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { UploadCustomRequestOptions, UploadFileInfo } from 'naive-ui';
import { fetchUploadImage, fetchUploadOptions } from '@/service/api/upload';
import ImageUpload from '../image-upload.vue';

vi.mock('@/locales', () => ({ $t: (key: string) => key }));
vi.mock('@/utils/image', () => ({
  imageUrls: (value: string | string[] | null) =>
    Array.isArray(value) ? value : (value || '').split(',').filter(Boolean),
  imageSrc: (value: string) => `http://api.test${value}`
}));
vi.mock('@/service/api/upload', () => ({ fetchUploadImage: vi.fn(), fetchUploadOptions: vi.fn() }));

const Upload = defineComponent({
  name: 'NUpload',
  props: ['fileList', 'customRequest', 'disabled', 'onBeforeUpload'],
  emits: ['update:file-list'],
  template: '<div><slot /></div>'
});

function file(id: string): UploadFileInfo {
  return { id, name: `${id}.png`, status: 'pending', file: new File(['image'], `${id}.png`, { type: 'image/png' }) };
}

function deferred() {
  let resolve!: (value: any) => void;
  const promise = new Promise<any>(done => {
    resolve = done;
  });
  return { promise, resolve };
}

function setup(value: string | string[] = '') {
  const wrapper = mount(ImageUpload, {
    props: { value, 'onUpdate:value': (next: any) => wrapper.setProps({ value: next }) },
    global: { stubs: { NUpload: Upload } }
  });
  const upload = wrapper.findComponent(Upload);
  const setFiles = (list: UploadFileInfo[]) => upload.vm.$emit('update:file-list', list);
  function start(item: UploadFileInfo) {
    const options = {
      file: item,
      onFinish: vi.fn(() =>
        setFiles(
          upload
            .props('fileList')
            .map((entry: UploadFileInfo) => (entry.id === item.id ? { ...item, status: 'finished' } : entry))
        )
      ),
      onError: vi.fn(() =>
        setFiles(
          upload
            .props('fileList')
            .map((entry: UploadFileInfo) => (entry.id === item.id ? { ...item, status: 'error' } : entry))
        )
      ),
      onProgress: vi.fn()
    };
    const task = upload.props('customRequest')(options as unknown as UploadCustomRequestOptions);
    return { ...options, task };
  }
  return { wrapper, upload, setFiles, start };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(fetchUploadOptions).mockResolvedValue({ data: { maxSizeMb: 2, extensions: ['png'] }, error: null } as any);
});

describe('image upload model lifecycle', () => {
  it('preserves selection order when concurrent uploads finish out of order', async () => {
    const first = deferred();
    const second = deferred();
    vi.mocked(fetchUploadImage).mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
    const { wrapper, setFiles, start } = setup();
    await flushPromises();
    const a = file('a'),
      b = file('b');
    setFiles([a, b]);
    await flushPromises();
    const requestA = start(a),
      requestB = start(b);
    second.resolve({ data: { url: '/b' }, error: null });
    await requestB.task;
    await flushPromises();
    expect(wrapper.props('value')).toBe('/b');
    first.resolve({ data: { url: '/a' }, error: null });
    await requestA.task;
    await flushPromises();
    expect(wrapper.props('value')).toBe('/a,/b');
    expect(wrapper.emitted('update:busy')?.at(-1)).toEqual([false]);
    wrapper.unmount();
  });

  it('aborts removed uploads and ignores late completions', async () => {
    const pending = deferred();
    vi.mocked(fetchUploadImage).mockReturnValue(pending.promise);
    const { wrapper, setFiles, start } = setup(['/existing']);
    await flushPromises();
    const item = file('new');
    setFiles([item]);
    await flushPromises();
    const request = start(item);
    const signal = vi.mocked(fetchUploadImage).mock.calls[0][1]!;
    setFiles([]);
    await flushPromises();
    expect(signal.aborted).toBe(true);
    pending.resolve({ data: { url: '/late' }, error: null });
    await request.task;
    await flushPromises();
    expect(wrapper.props('value')).toEqual([]);
    expect(request.onFinish).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it('does not persist failed files and allows retry', async () => {
    vi.mocked(fetchUploadImage)
      .mockResolvedValueOnce({ data: null, error: new Error('failure') } as any)
      .mockResolvedValueOnce({ data: { url: '/retried' }, error: null } as any);
    const { wrapper, setFiles, start } = setup();
    await flushPromises();
    const item = file('retry');
    setFiles([item]);
    await flushPromises();
    await start(item).task;
    await flushPromises();
    expect(wrapper.props('value')).toBe('');
    await start(item).task;
    await flushPromises();
    expect(wrapper.props('value')).toBe('/retried');
    wrapper.unmount();
  });

  it('rejects invalid types and oversize files before requests', async () => {
    const { wrapper, upload } = setup();
    await flushPromises();
    const before = upload.props('onBeforeUpload');
    expect(before({ file: { ...file('bad'), file: new File(['svg'], 'bad.svg') } })).toBe(false);
    expect(
      before({ file: { ...file('large'), file: new File([new Uint8Array(2 * 1024 * 1024 + 1)], 'large.png') } })
    ).toBe(false);
    expect(fetchUploadImage).not.toHaveBeenCalled();
    wrapper.unmount();
  });
});
