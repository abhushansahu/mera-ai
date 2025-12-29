"use client";

import { ChatInterface } from '@/components/chat/ChatInterface';
import { RPIWorkflow } from '@/components/workflow/RPIWorkflow';
import { AgentFlow } from '@/components/agents/AgentFlow';
import { SpacesDashboard } from '@/components/spaces/SpacesDashboard';
import { MemoryGraph } from '@/components/memory/MemoryGraph';
import { ContextPanel } from '@/components/context/ContextPanel';
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';
import { useTheme } from '@/hooks/useTheme';
import { useState } from 'react';

export default function Home() {
  const [activeTab, setActiveTab] = useState<'chat' | 'spaces'>('chat');
  const { theme, toggleTheme } = useTheme();

  return (
    <ErrorBoundary>
      <div className="flex h-screen overflow-hidden">
        <div className="flex-1 flex flex-col min-w-0">
        <div className="border-b p-4 bg-white dark:bg-gray-900 flex-shrink-0">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Mera AI</h1>
            <div className="flex items-center gap-2">
              <button
                onClick={toggleTheme}
                className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                aria-label="Toggle theme"
              >
                {theme === 'dark' ? '☀️' : '🌙'}
              </button>
              <button
                onClick={() => setActiveTab('chat')}
                className={`px-4 py-2 rounded-lg transition-colors ${
                  activeTab === 'chat'
                    ? 'bg-blue-500 text-white shadow-md'
                    : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
                }`}
              >
                Chat
              </button>
              <button
                onClick={() => setActiveTab('spaces')}
                className={`px-4 py-2 rounded-lg transition-colors ${
                  activeTab === 'spaces'
                    ? 'bg-blue-500 text-white shadow-md'
                    : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
                }`}
              >
                Spaces
              </button>
            </div>
          </div>
        </div>
        
        {activeTab === 'chat' && (
          <div className="flex-1 flex min-h-0">
            <div className="flex-1 flex flex-col min-w-0">
              <div className="p-4 border-b bg-gray-50 dark:bg-gray-800 flex-shrink-0">
                <h2 className="font-bold mb-2 text-gray-900 dark:text-white">RPI Workflow</h2>
                <div className="h-64 min-h-[256px]">
                  <RPIWorkflow />
                </div>
              </div>
              <div className="flex-1 min-h-0">
                <ChatInterface />
              </div>
            </div>
            <ContextPanel />
          </div>
        )}
        
        {activeTab === 'spaces' && (
          <div className="flex-1 overflow-y-auto min-h-0">
            <SpacesDashboard />
            <div className="p-4">
              <h2 className="font-bold mb-2 text-gray-900 dark:text-white">Memory Graph</h2>
              <MemoryGraph />
            </div>
          </div>
        )}
        </div>
      </div>
    </ErrorBoundary>
  );
}
