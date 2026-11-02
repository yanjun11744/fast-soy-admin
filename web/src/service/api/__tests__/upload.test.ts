import { beforeEach, describe, expect, it, vi } from 'vitest';
import { request } from '../../request';
import { fetchUploadImage } from '../upload';

vi.mock('../../request', () => ({ request: vi.fn() }));

describe('upload transport', () => {
  beforeEach(() => vi.clearAllMocks());

  it('sends multipart instead of the shared JSON default and supports cancellation', () => {
    const file = new File(['png'], 'image.png', { type: 'image/png' });
    const controller = new AbortController();
    const progress = vi.fn();
    fetchUploadImage(file, controller.signal, progress);
    const config = vi.mocked(request).mock.calls[0][0] as any;
    expect(config.headers['Content-Type']).toBe('multipart/form-data');
    expect(config.data).toBeInstanceOf(FormData);
    expect(config.data.get('file')).toBe(file);
    expect(config.signal).toBe(controller.signal);
    config.onUploadProgress({ loaded: 3, total: 3 });
    expect(progress).toHaveBeenCalledWith(99);
  });
});
