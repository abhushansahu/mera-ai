"use client";

import { useMemo, useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { shallow } from 'zustand/shallow';

export function ContextPanel() {
  const { workflowState, agentActivity, activeThreadId, threads, obsidianSession, obsidianSyncStatus } = useAppStore(
    (state) => ({
      workflowState: state.workflowState,
      agentActivity: state.agentActivity,
      activeThreadId: state.activeThreadId,
      threads: state.threads,
      obsidianSession: state.obsidianSession,
      obsidianSyncStatus: state.obsidianSyncStatus,
    }),
    shallow
  );
  const [isCollapsed, setIsCollapsed] = useState(false);
  const recentEvents = useMemo(() => (obsidianSession?.recent_events || []).slice(-8).reverse(), [obsidianSession]);

  if (isCollapsed) {
    return (
      <button
        onClick={() => setIsCollapsed(false)}
        className="w-8 border-l p-2 bg-gray-50 dark:bg-gray-900 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
        aria-label="Expand context panel"
      >
        ▶
      </button>
    );
  }

  return (
    <div className="w-80 border-l border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 h-full overflow-y-auto flex-shrink-0">
      <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
        <h3 className="font-bold text-lg text-gray-900 dark:text-white">Context</h3>
        <button
          onClick={() => setIsCollapsed(true)}
          className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors"
          aria-label="Collapse context panel"
        >
          ◀
        </button>
      </div>
      
      <div className="p-4 space-y-4">
        <div className="bg-white dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-700 shadow-sm">
          <h4 className="font-semibold mb-2 text-gray-900 dark:text-white">Obsidian Session</h4>
          <div className="text-xs space-y-1 text-gray-600 dark:text-gray-300">
            <div>
              Status:{' '}
              <span
                className={
                  obsidianSyncStatus === 'live'
                    ? 'text-emerald-600 dark:text-emerald-400'
                    : obsidianSyncStatus === 'error'
                      ? 'text-red-600 dark:text-red-400'
                      : 'text-gray-500 dark:text-gray-400'
                }
              >
                {obsidianSyncStatus}
              </span>
            </div>
            {obsidianSession?.last_heartbeat_age_ms != null && (
              <div>
                Heartbeat age: {Math.round(obsidianSession.last_heartbeat_age_ms / 1000)}s
              </div>
            )}
            <div className="font-medium text-gray-900 dark:text-white">
              {obsidianSession?.active_note_title || 'No active note'}
            </div>
            <div className="truncate">{obsidianSession?.active_note_path || 'Waiting for plugin events...'}</div>
            {obsidianSession?.active_selection && (
              <div className="rounded bg-gray-100 dark:bg-gray-700 p-2 text-[11px] max-h-24 overflow-y-auto">
                {obsidianSession.active_selection}
              </div>
            )}
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-700 shadow-sm">
          <h4 className="font-semibold mb-2 text-gray-900 dark:text-white">Workflow Stage</h4>
          <div className="text-sm">
            <div className={`inline-block px-3 py-1 rounded-full font-medium ${
              workflowState.stage === 'idle' ? 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300' :
              workflowState.stage === 'research' ? 'bg-blue-200 dark:bg-blue-800 text-blue-800 dark:text-blue-200' :
              workflowState.stage === 'plan' ? 'bg-amber-200 dark:bg-amber-800 text-amber-800 dark:text-amber-200' :
              workflowState.stage === 'implement' ? 'bg-green-200 dark:bg-green-800 text-green-800 dark:text-green-200' :
              'bg-purple-200 dark:bg-purple-800 text-purple-800 dark:text-purple-200'
            }`}>
              {workflowState.stage}
            </div>
          </div>
        </div>

        {activeThreadId && (
          <div className="bg-white dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-700 shadow-sm">
            <h4 className="font-semibold mb-2 text-gray-900 dark:text-white">Active Thread</h4>
            <div className="text-xs text-gray-600 dark:text-gray-300">
              {threads.find((thread) => thread.id === activeThreadId)?.title || activeThreadId}
            </div>
          </div>
        )}

        <div className="bg-white dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-700 shadow-sm">
          <h4 className="font-semibold mb-2 text-gray-900 dark:text-white">Recent Note Events</h4>
          {recentEvents.length === 0 ? (
            <div className="text-xs text-gray-500 dark:text-gray-400">No events yet.</div>
          ) : (
            <div className="space-y-2">
              {recentEvents.map((event) => (
                <div key={event.event_id} className="rounded border border-gray-200 dark:border-gray-700 p-2 text-xs">
                  <div className="font-medium text-gray-900 dark:text-white">
                    {event.event_type} · {event.note_title || event.note_path}
                  </div>
                  <div className="truncate text-gray-600 dark:text-gray-300">{event.note_path}</div>
                  {event.clicked_target && (
                    <div className="text-gray-500 dark:text-gray-400">target: {event.clicked_target}</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {agentActivity && Object.keys(agentActivity).length > 0 && (
          <div className="bg-white dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-700 shadow-sm">
            <h4 className="font-semibold mb-2 text-gray-900 dark:text-white">Agent Activity</h4>
            <pre className="text-xs text-gray-600 dark:text-gray-300 whitespace-pre-wrap">
              {JSON.stringify(agentActivity, null, 2)}
            </pre>
          </div>
        )}

        {workflowState.metadata && Object.keys(workflowState.metadata).length > 0 && (
          <div className="bg-white dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-700 shadow-sm">
            <h4 className="font-semibold mb-2 text-gray-900 dark:text-white">Metadata</h4>
            <div className="text-sm space-y-2">
              {Object.entries(workflowState.metadata).map(([key, value]) => (
                <div key={key} className="flex justify-between">
                  <span className="font-medium text-gray-700 dark:text-gray-300">{key}:</span>
                  <span className="text-gray-600 dark:text-gray-400">{String(value)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
