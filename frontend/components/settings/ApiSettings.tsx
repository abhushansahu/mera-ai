"use client";

import { FormEvent, useState } from 'react';
import {
  defaultApiUrl,
  getRuntimeApiUrl,
  setRuntimeApiUrl,
} from '@/lib/config/runtime';

export function ApiSettings() {
  const [apiUrl, setApiUrl] = useState(getRuntimeApiUrl());
  const [saved, setSaved] = useState(false);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    setRuntimeApiUrl(apiUrl);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  const resetDefault = () => {
    setRuntimeApiUrl(defaultApiUrl);
    setApiUrl(defaultApiUrl);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  return (
    <form onSubmit={onSubmit} className="rounded-lg border border-gray-200 dark:border-gray-700 p-3 bg-white dark:bg-gray-900">
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
    </form>
  );
}
