const API_URL_KEY = 'mera_api_url';

export const defaultApiUrl =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8081';

export function getRuntimeApiUrl(): string {
  if (typeof window === 'undefined') {
    return defaultApiUrl;
  }
  const stored = window.localStorage.getItem(API_URL_KEY);
  return stored && stored.trim() ? stored : defaultApiUrl;
}

export function setRuntimeApiUrl(url: string): void {
  if (typeof window === 'undefined') {
    return;
  }
  const normalized = url.trim().replace(/\/+$/, '');
  if (!normalized) {
    window.localStorage.removeItem(API_URL_KEY);
    return;
  }
  window.localStorage.setItem(API_URL_KEY, normalized);
}
