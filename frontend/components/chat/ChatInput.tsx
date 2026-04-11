"use client";

import { useAppStore } from '@/store/useAppStore';
import { featureFlags } from '@/lib/config/features';
import { getRuntimeProvider, setRuntimeProvider } from '@/lib/config/runtime';
import { useEffect, useMemo, useState } from 'react';
import { shallow } from 'zustand/shallow';
import { MODELS_BY_PROVIDER, PROVIDER_OPTIONS } from '@/lib/config/models';
import { ContextSourceType } from '@/lib/types/contracts';

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  isLoading: boolean;
}

export function ChatInput({ value, onChange, onSend, isLoading }: ChatInputProps) {
  const {
    clearMessages,
    defaultModel,
    defaultProvider,
    setDefaultModel,
    setDefaultProvider,
    pendingContextSources,
    setPendingContextSources,
    obsidianSession,
  } = useAppStore(
    (state) => ({
      clearMessages: state.clearMessages,
      defaultModel: state.defaultModel,
      defaultProvider: state.defaultProvider,
      setDefaultModel: state.setDefaultModel,
      setDefaultProvider: state.setDefaultProvider,
      pendingContextSources: state.pendingContextSources,
      setPendingContextSources: state.setPendingContextSources,
      obsidianSession: state.obsidianSession,
    }),
    shallow
  );
  const [contextPath, setContextPath] = useState('');
  const [contextType, setContextType] = useState<ContextSourceType>('FILE');
  const modelOptions = useMemo(() => MODELS_BY_PROVIDER[defaultProvider] || MODELS_BY_PROVIDER.openrouter, [defaultProvider]);

  useEffect(() => {
    const runtimeProvider = getRuntimeProvider();
    if (runtimeProvider && runtimeProvider !== defaultProvider) {
      setDefaultProvider(runtimeProvider);
    }
  }, [defaultProvider, setDefaultProvider]);

  useEffect(() => {
    if (!modelOptions.includes(defaultModel) && modelOptions.length > 0) {
      setDefaultModel(modelOptions[0]);
    }
  }, [defaultModel, modelOptions, setDefaultModel]);

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <div className="border-t dark:border-gray-700 p-4 bg-white dark:bg-gray-900 flex-shrink-0">
      {featureFlags.perMessageModel && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-2 mb-3">
          <div>
            <label className="block text-xs font-semibold text-gray-600 dark:text-gray-300 mb-1">Provider</label>
            <select
              value={defaultProvider}
              onChange={(e) => {
                const nextProvider = e.target.value;
                const nextModels = MODELS_BY_PROVIDER[nextProvider] || MODELS_BY_PROVIDER.openrouter;
                setDefaultProvider(nextProvider);
                setRuntimeProvider(nextProvider);
                if (!nextModels.includes(defaultModel) && nextModels.length > 0) {
                  setDefaultModel(nextModels[0]);
                }
              }}
              className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-2 py-1 text-sm"
            >
              {PROVIDER_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-600 dark:text-gray-300 mb-1">Model</label>
            <select
              value={defaultModel}
              onChange={(e) => setDefaultModel(e.target.value)}
              className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-2 py-1 text-sm"
            >
              {modelOptions.map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-600 dark:text-gray-300 mb-1">Context Type</label>
            <select
              value={contextType}
              onChange={(e) => setContextType(e.target.value as ContextSourceType)}
              className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-2 py-1 text-sm"
            >
              <option value="FILE">File</option>
              <option value="DIRECTORY">Directory</option>
              <option value="URL">URL</option>
              <option value="MEMORY">Memory</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-600 dark:text-gray-300 mb-1">Context Path</label>
            <div className="flex gap-2">
              <input
                value={contextPath}
                onChange={(e) => setContextPath(e.target.value)}
                className="flex-1 rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-2 py-1 text-sm"
                placeholder="path, URL, or memory query"
              />
              <button
                type="button"
                onClick={() => {
                  if (!contextPath.trim()) return;
                  setPendingContextSources([
                    ...pendingContextSources,
                    { type: contextType, path: contextPath.trim() },
                  ]);
                  setContextPath('');
                }}
                className="px-2 py-1 text-xs rounded-md bg-gray-200 dark:bg-gray-700"
              >
                Add
              </button>
            </div>
          </div>
        </div>
      )}
      {pendingContextSources.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-2">
          {pendingContextSources.map((source, index) => (
            <button
              type="button"
              key={`${source.type}-${source.path}-${index}`}
              onClick={() =>
                setPendingContextSources(
                  pendingContextSources.filter((_, sourceIndex) => sourceIndex !== index)
                )
              }
              className="text-xs px-2 py-1 rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200"
            >
              {source.type}:{source.path} ×
            </button>
          ))}
          <button
            type="button"
            className="text-xs text-gray-500 hover:text-gray-800 dark:hover:text-gray-100"
            onClick={() => setPendingContextSources([])}
          >
            Clear context
          </button>
        </div>
      )}
      {featureFlags.obsidianAdvanced && (
        <div className="mb-3 border rounded-lg p-2 border-gray-200 dark:border-gray-700">
          <div className="text-xs font-semibold mb-1 text-gray-600 dark:text-gray-300">Live Obsidian Context</div>
          <div className="text-xs text-gray-600 dark:text-gray-300">
            {obsidianSession?.active_note_path ? (
              <>
                <div className="font-medium">{obsidianSession.active_note_title || obsidianSession.active_note_path}</div>
                <div className="truncate">{obsidianSession.active_note_path}</div>
                <div className="mt-1">{(obsidianSession.recent_events || []).length} recent events attached automatically.</div>
              </>
            ) : (
              <div>No active note detected yet. Open or click in Obsidian to stream context here.</div>
            )}
          </div>
        </div>
      )}
      <div className="flex gap-2 items-end">
        <div className="flex-1">
          <textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyPress}
            placeholder="Ask a question... (Press Enter to send, Shift+Enter for new line)"
            className="w-full p-3 border border-gray-300 dark:border-gray-600 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400 transition-all"
            rows={3}
            disabled={isLoading}
          />
        </div>
        <div className="flex flex-col gap-2">
          <button
            onClick={onSend}
            disabled={isLoading || !value.trim()}
            className="px-6 py-3 bg-gradient-primary text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-lg transition-all font-medium"
          >
            {isLoading ? (
              <span className="flex items-center gap-2">
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
                Sending...
              </span>
            ) : (
              'Send'
            )}
          </button>
          <button
            onClick={clearMessages}
            className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 transition-colors"
            title="Clear conversation"
          >
            Clear
          </button>
        </div>
      </div>
    </div>
  );
}
