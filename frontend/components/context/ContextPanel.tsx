"use client";

import { useState } from 'react';
import { useAppStore } from '@/store/useAppStore';

export function ContextPanel() {
  const { currentSpace, workflowState, agentActivity, spaces, setCurrentSpace } = useAppStore();
  const [isCollapsed, setIsCollapsed] = useState(false);

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
        {currentSpace && (
          <div className="bg-white dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-700 shadow-sm">
            <h4 className="font-semibold mb-2 text-gray-900 dark:text-white">Current Space</h4>
            <div className="text-sm space-y-1">
              <div className="font-medium text-gray-900 dark:text-white">{currentSpace.name}</div>
              <div className="text-gray-600 dark:text-gray-400 text-xs">{currentSpace.space_id}</div>
              <div className="mt-2">
                <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Token Budget</div>
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                  <div
                    className="bg-blue-500 h-2 rounded-full transition-all"
                    style={{ width: '75%' }}
                  ></div>
                </div>
                <div className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                  {currentSpace.monthly_token_budget.toLocaleString()} tokens
                </div>
              </div>
            </div>
          </div>
        )}

        {spaces.length > 0 && (
          <div className="bg-white dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-700 shadow-sm">
            <h4 className="font-semibold mb-2 text-gray-900 dark:text-white">Switch Space</h4>
            <select
              value={currentSpace?.space_id || ''}
              onChange={(e) => {
                const space = spaces.find(s => s.space_id === e.target.value);
                if (space) setCurrentSpace(space);
              }}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm"
            >
              <option value="">Select a space...</option>
              {spaces.map((space) => (
                <option key={space.space_id} value={space.space_id}>
                  {space.name}
                </option>
              ))}
            </select>
          </div>
        )}

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
