"use client";

import { FormEvent, useState } from 'react';
import {
  defaultApiUrl,
  getRuntimeApiUrl,
  getRuntimeAuthToken,
  getRuntimeUserId,
  setRuntimeApiUrl,
  setRuntimeAuthToken,
  setRuntimeUserId,
} from '@/lib/config/runtime';
import { chatApi } from '@/lib/api/client';
import { featureFlags } from '@/lib/config/features';
import { PROVIDER_OPTIONS } from '@/lib/config/models';

export function ApiSettings() {
  const [apiUrl, setApiUrl] = useState(getRuntimeApiUrl());
  const [saved, setSaved] = useState(false);
  const [ownerId, setOwnerId] = useState(getRuntimeUserId());
  const [userId, setUserId] = useState(getRuntimeUserId());
  const [authToken, setAuthToken] = useState(getRuntimeAuthToken());
  const [provider, setProvider] = useState('openrouter');
  const [providerKey, setProviderKey] = useState('');
  const [providerStatus, setProviderStatus] = useState<string>('');
  const [settingsError, setSettingsError] = useState<string>('');

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    setRuntimeApiUrl(apiUrl);
    setRuntimeAuthToken(authToken);
    setRuntimeUserId(userId);
    setOwnerId(userId || ownerId);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  const resetDefault = () => {
    setRuntimeApiUrl(defaultApiUrl);
    setApiUrl(defaultApiUrl);
    setRuntimeAuthToken('');
    setAuthToken('');
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-3 bg-white dark:bg-gray-900 space-y-4">
      <form onSubmit={onSubmit}>
        <label className="block text-xs font-semibold text-gray-600 dark:text-gray-300 mb-1">
          API Base URL
        </label>
        <input
          value={apiUrl}
          onChange={(e) => setApiUrl(e.target.value)}
          className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-2 py-1 text-sm"
          placeholder="http://localhost:8081"
        />
        <div className="mt-2 flex items-center gap-2">
          <button
            type="submit"
            className="px-2 py-1 text-xs rounded-md bg-blue-600 text-white hover:bg-blue-700"
          >
            Save
          </button>
          <button
            type="button"
            onClick={resetDefault}
            className="px-2 py-1 text-xs rounded-md border border-gray-300 dark:border-gray-700"
          >
            Reset
          </button>
          {saved && <span className="text-xs text-green-600 dark:text-green-400">Saved</span>}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-3">
          <input
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            className="rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-2 py-1 text-sm"
            placeholder="User id (for local/dev mode)"
          />
          <input
            value={authToken}
            onChange={(e) => setAuthToken(e.target.value)}
            className="rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-2 py-1 text-sm"
            placeholder="Bearer token (optional in dev)"
          />
        </div>
      </form>
      {featureFlags.secureProviderSettings && (
        <div className="border-t border-gray-200 dark:border-gray-700 pt-3">
          <div className="text-xs font-semibold text-gray-600 dark:text-gray-300 mb-2">
            Secure Provider Credentials (server-managed)
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <input
              value={ownerId}
              onChange={(e) => setOwnerId(e.target.value)}
              className="rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-2 py-1 text-sm"
              placeholder="owner id"
            />
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-2 py-1 text-sm"
            >
              {PROVIDER_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <input
              type="password"
              value={providerKey}
              onChange={(e) => setProviderKey(e.target.value)}
              className="rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-2 py-1 text-sm"
              placeholder={provider === 'openrouter' ? 'api key' : 'optional token'}
            />
          </div>
          <div className="mt-2 flex items-center gap-2">
            <button
              type="button"
              onClick={async () => {
                setSettingsError('');
                try {
                  const result = await chatApi.saveProviderKey({
                    owner_id: ownerId,
                    provider,
                    api_key: providerKey,
                  });
                  setProviderStatus(`Saved (${result.provider}) ending in ${result.last4}`);
                  setProviderKey('');
                } catch (error) {
                  setSettingsError(error instanceof Error ? error.message : 'Failed to save provider key.');
                }
              }}
              className="px-2 py-1 text-xs rounded-md bg-emerald-600 text-white hover:bg-emerald-700"
            >
              Save Key
            </button>
            <button
              type="button"
              onClick={async () => {
                setSettingsError('');
                try {
                  const status = await chatApi.getProviderKeyStatus({
                    owner_id: ownerId,
                    provider,
                  });
                  setProviderStatus(`Active key for ${status.provider} ends with ${status.last4}`);
                } catch (error) {
                  setSettingsError(error instanceof Error ? error.message : 'Failed to fetch provider key status.');
                }
              }}
              className="px-2 py-1 text-xs rounded-md border border-gray-300 dark:border-gray-700"
            >
              Check Status
            </button>
            {providerStatus && <span className="text-xs text-gray-600 dark:text-gray-300">{providerStatus}</span>}
          </div>
          {settingsError && <div className="mt-2 text-xs text-red-600 dark:text-red-400">{settingsError}</div>}
        </div>
      )}
    </div>
  );
}
