import { request } from '../request';

export interface UploadedImage {
  id: string;
  key: string;
  name: string;
  url: string;
  mediaType: string;
  size: number;
  width: number;
  height: number;
  fmtCreatedAt: string;
}

export interface UploadSetting {
  storageRoot: string;
  maxSizeMb: number;
}

export function fetchUploadOptions() {
  return request<{ maxSizeMb: number; extensions: string[] }>({ url: '/system-manage/uploads/options' });
}

export function fetchUploadSettings() {
  return request<UploadSetting>({ url: '/system-manage/uploads/settings' });
}

export function fetchUpdateUploadSettings(data: UploadSetting) {
  return request<UploadSetting>({ url: '/system-manage/uploads/settings', method: 'patch', data });
}

export function fetchUploadImage(file: File, signal?: AbortSignal, onProgress?: (percentage: number) => void) {
  const data = new FormData();
  data.append('file', file);
  return request<UploadedImage>({
    url: '/system-manage/uploads/images',
    method: 'post',
    data,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
    signal,
    onUploadProgress: event => onProgress?.(Math.min(99, Math.round((event.loaded / (event.total || file.size)) * 100)))
  });
}

export function fetchUploadedImages(data: { current: number; size: number; name?: string }) {
  return request<{ records: UploadedImage[]; total: number }>({
    url: '/system-manage/uploads/search',
    method: 'post',
    data
  });
}
