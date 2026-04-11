const API_URL_KEY = 'mera_api_url';
const AUTH_TOKEN_KEY = 'mera_auth_token';
const USER_ID_KEY = 'mera_user_id';
const PROVIDER_KEY = 'mera_provider';

export const defaultApiUrl =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8081';
export const defaultProvider = process.env.NEXT_PUBLIC_DEFAULT_PROVIDER || 'openrouter';

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

export function getRuntimeAuthToken(): string {
  if (typeof window === 'undefined') {
    return process.env.NEXT_PUBLIC_AUTH_TOKEN || '';
  }
  return window.localStorage.getItem(AUTH_TOKEN_KEY) || process.env.NEXT_PUBLIC_AUTH_TOKEN || '';
}

export function setRuntimeAuthToken(token: string): void {
  if (typeof window === 'undefined') {
    return;
  }
  const normalized = token.trim();
  if (!normalized) {
    window.localStorage.removeItem(AUTH_TOKEN_KEY);
    return;
  }
  window.localStorage.setItem(AUTH_TOKEN_KEY, normalized);
}

export function getRuntimeUserId(): string {
  if (typeof window === 'undefined') {
    return process.env.NEXT_PUBLIC_USER_ID || 'default-user';
  }
  return window.localStorage.getItem(USER_ID_KEY) || process.env.NEXT_PUBLIC_USER_ID || 'default-user';
}

export function setRuntimeUserId(userId: string): void {
  if (typeof window === 'undefined') {
    return;
  }
  const normalized = userId.trim();
  if (!normalized) {
    window.localStorage.removeItem(USER_ID_KEY);
    return;
  }
  window.localStorage.setItem(USER_ID_KEY, normalized);
}

export function getRuntimeProvider(): string {
  if (typeof window === 'undefined') {
    return defaultProvider;
  }
  return window.localStorage.getItem(PROVIDER_KEY) || defaultProvider;
}

export function setRuntimeProvider(provider: string): void {
  if (typeof window === 'undefined') {
    return;
  }
  const normalized = provider.trim();
  if (!normalized) {
    window.localStorage.removeItem(PROVIDER_KEY);
    return;
  }
  window.localStorage.setItem(PROVIDER_KEY, normalized);
}
