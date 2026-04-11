"use client";

import { ChatInterface } from '@/components/chat/ChatInterface';
import { ApiSettings } from '@/components/settings/ApiSettings';
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';
import { useTheme } from '@/hooks/useTheme';
import { useEffect, useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { featureFlags, hydrateFeatureFlags } from '@/lib/config/features';
import { ContextPanel } from '@/components/context/ContextPanel';
import { shallow } from 'zustand/shallow';

export default function Home() {
  const [showSettings, setShowSettings] = useState(false);
  const [, setFlagsVersion] = useState(0);
  const { theme, toggleTheme } = useTheme();
  const { threads, activeThreadId, setActiveThreadId, obsidianSession } = useAppStore(
    (state) => ({
      threads: state.threads,
      activeThreadId: state.activeThreadId,
      setActiveThreadId: state.setActiveThreadId,
      obsidianSession: state.obsidianSession,
    }),
    shallow
  );

  useEffect(() => {
    hydrateFeatureFlags().finally(() => setFlagsVersion((value) => value + 1));
  }, []);

  return (
    <ErrorBoundary>
      <div className="flex h-screen overflow-hidden">
        <div className="flex-1 flex flex-col min-w-0">
        <div className="border-b p-4 bg-white dark:bg-gray-900 flex-shrink-0">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Mera x Obsidian</h1>
              <div className="text-xs text-gray-500 dark:text-gray-400">
                Assistant is auto-scoped to the active note and recent Obsidian interactions.
              </div>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <button
                onClick={toggleTheme}
                className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                aria-label="Toggle theme"
              >
                <span aria-hidden>{theme === 'dark' ? '☀️' : '🌙'}</span>
                <span className="sr-only">Toggle theme</span>
              </button>
              <button
                onClick={() => setShowSettings((prev) => !prev)}
                className="px-3 py-2 rounded-lg bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-sm"
                aria-expanded={showSettings}
                aria-controls="settings-panel"
              >
                Settings
              </button>
            </div>
          </div>
        </div>
        {showSettings && (
          <div id="settings-panel" className="border-b p-3 bg-gray-50 dark:bg-gray-900">
            <ApiSettings />
          </div>
        )}
        <div className="flex-1 flex min-h-0">
            <aside className="w-80 border-r border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 p-3 overflow-y-auto flex-shrink-0">
              <div className="mb-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-3">
                <div className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Active Note</div>
                <div className="mt-1 font-medium text-gray-900 dark:text-white">
                  {obsidianSession?.active_note_title || 'No note detected'}
                </div>
                <div className="mt-1 text-xs truncate text-gray-600 dark:text-gray-300">
                  {obsidianSession?.active_note_path || 'Open a note in Obsidian to attach context.'}
                </div>
              </div>
              <div className="mb-2 text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Sessions / Threads</div>
              <div className="space-y-2">
                {threads.map((thread) => (
                  <button
                    key={thread.id}
                    type="button"
                    onClick={() => setActiveThreadId(thread.id)}
                    className={`w-full text-left rounded-lg border px-3 py-2 text-sm transition-colors ${
                      activeThreadId === thread.id
                        ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200'
                        : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 hover:border-gray-300 dark:hover:border-gray-500'
                    }`}
                  >
                    <div className="font-medium truncate">{thread.title}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 truncate">{thread.id}</div>
                  </button>
                ))}
              </div>
            </aside>
            <div className="flex-1 flex flex-col min-w-0">
              <div className="px-4 py-2 border-b border-gray-200 dark:border-gray-700 text-xs text-gray-600 dark:text-gray-300">
                {featureFlags.obsidianEventSync ? 'Live Obsidian context sync enabled.' : 'Obsidian live sync disabled.'}
              </div>
              <div className="flex-1 min-h-0">
                  <ChatInterface />
              </div>
            </div>
            <ContextPanel />
          </div>
        </div>
      </div>
    </ErrorBoundary>
  );
}
