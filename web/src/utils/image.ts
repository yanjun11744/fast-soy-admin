import { getServiceBaseURL } from './service';

export type ImageValue = string | string[] | null | undefined;

/** Persist backend-relative paths, resolve the current proxy/origin only for display. */
export function imageUrls(value: ImageValue): string[] {
  const items = Array.isArray(value) ? value : (value || '').split(',');
  return items.map(item => item.trim()).filter(Boolean);
}

export function imageSrc(value: string): string {
  if (/^https?:\/\//i.test(value)) return value;
  if (!value.startsWith('/') || value.startsWith('//')) return '';
  const proxy = import.meta.env.DEV && import.meta.env.VITE_HTTP_PROXY === 'Y';
  const { baseURL } = getServiceBaseURL(import.meta.env, proxy);
  if (value.startsWith('/system-manage/uploads/content/')) return `${baseURL.replace(/\/$/, '')}${value}`;
  // Existing root-relative image URLs keep their server origin in deployments with a separate API host.
  if (/^https?:\/\//i.test(baseURL)) return `${new URL(baseURL).origin}${value}`;
  return value;
}
