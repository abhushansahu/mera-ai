"use client";

import { useEffect, useMemo, useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { chatApi, ChatRequest } from '@/lib/api/client';
import { useWorkflowStream } from '@/hooks/useWorkflowStream';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';
import { featureFlags } from '@/lib/config/features';
import { getRuntimeUserId } from '@/lib/config/runtime';
import { shallow } from 'zustand/shallow';
import { ContextSourceContract } from '@/lib/types/contracts';

const toRuntimeMessage = (message: Awaited<ReturnType<typeof chatApi.listThreadMessages>>[number]) => ({
  id: message.id,
  threadId: message.thread_id,
  role: (message.role as 'user' | 'assistant' | 'research' | 'plan') ?? 'assistant',
  content: message.content,
  timestamp: new Date(message.created_at),
  metadata: message.metadata,
});

export function ChatInterface() {
  const messagesByThread = useAppStore((state) => state.messagesByThread);
  const workflowState = useAppStore((state) => state.workflowState);
  const activeThreadId = useAppStore((state) => state.activeThreadId);
  const currentSpace = useAppStore((state) => state.currentSpace);
  const defaultModel = useAppStore((state) => state.defaultModel);
  const defaultProvider = useAppStore((state) => state.defaultProvider);
  const pendingContextSources = useAppStore((state) => state.pendingContextSources);
  const obsidianSession = useAppStore((state) => state.obsidianSession);
  const obsidianSyncStatus = useAppStore((state) => state.obsidianSyncStatus);
  const {
    addMessage,
    updateMessage,
    setWorkflowState,
    setActiveThreadId,
    setThreads,
    setThreadMessages,
    setObsidianSession,
    setObsidianSyncStatus,
  } = useAppStore(
    (state) => ({
      addMessage: state.addMessage,
      updateMessage: state.updateMessage,
      setWorkflowState: state.setWorkflowState,
      setActiveThreadId: state.setActiveThreadId,
      setThreads: state.setThreads,
      setThreadMessages: state.setThreadMessages,
      setObsidianSession: state.setObsidianSession,
      setObsidianSyncStatus: state.setObsidianSyncStatus,
    }),
    shallow
  );
  const threads = useAppStore((state) => state.threads);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [threadsLoading, setThreadsLoading] = useState(false);
  const [threadsError, setThreadsError] = useState<string | null>(null);
  const { startStream, isStreaming } = useWorkflowStream();
  const userId = getRuntimeUserId();
  const [obsidianError, setObsidianError] = useState<string | null>(null);

  const messages = useMemo(() => {
    if (!activeThreadId) {
      return [];
    }
    return messagesByThread[activeThreadId] ?? [];
  }, [activeThreadId, messagesByThread]);

  useEffect(() => {
    if (!featureFlags.threading) {
      return;
    }
    const loadThreads = async () => {
      try {
        setThreadsLoading(true);
        setThreadsError(null);
        const allThreads = await chatApi.listThreads({
          user_id: userId,
          space_id: currentSpace?.space_id,
        });
        setThreads(allThreads);
        const nextThread = allThreads[0];
        if (nextThread) {
          setActiveThreadId(nextThread.id);
          const persisted = await chatApi.listThreadMessages({ thread_id: nextThread.id, user_id: userId });
          setThreadMessages(nextThread.id, persisted.map(toRuntimeMessage));
        }
      } catch (error) {
        setThreadsError(error instanceof Error ? error.message : 'Failed to load threads.');
      } finally {
        setThreadsLoading(false);
      }
    };
    loadThreads();
  }, [currentSpace?.space_id, setActiveThreadId, setThreadMessages, setThreads, userId]);

  useEffect(() => {
    if (!featureFlags.obsidianEventSync) {
      return;
    }
    let isCancelled = false;
    setObsidianSyncStatus('connecting');
    const syncObsidianContext = async () => {
      try {
        const session = await chatApi.getObsidianContextSession({
          user_id: userId,
          space_id: currentSpace?.space_id,
          session_id: 'default',
        });
        if (!isCancelled) {
          setObsidianSession(session);
          if (session.plugin_connected) {
            setObsidianSyncStatus('live');
          } else if (session.last_event_at) {
            setObsidianSyncStatus('idle');
          } else {
            setObsidianSyncStatus('connecting');
          }
          setObsidianError(null);
        }
      } catch (error) {
        if (!isCancelled) {
          setObsidianSyncStatus('error');
          setObsidianError(error instanceof Error ? error.message : 'Failed to sync Obsidian context.');
        }
      }
    };
    syncObsidianContext();
    const interval = window.setInterval(syncObsidianContext, 2500);
    return () => {
      isCancelled = true;
      window.clearInterval(interval);
    };
  }, [currentSpace?.space_id, setObsidianSession, setObsidianSyncStatus, userId]);

  useEffect(() => {
    if (!featureFlags.threading || !activeThreadId) {
      return;
    }
    const alreadyLoaded = (messagesByThread[activeThreadId] ?? []).length > 0;
    if (alreadyLoaded) {
      return;
    }
    const loadMessages = async () => {
      try {
        const persisted = await chatApi.listThreadMessages({ thread_id: activeThreadId, user_id: userId });
        setThreadMessages(activeThreadId, persisted.map(toRuntimeMessage));
      } catch (error) {
        console.error('Failed to load thread messages', error);
      }
    };
    loadMessages();
  }, [activeThreadId, messagesByThread, setThreadMessages, userId]);

  const ensureThread = async (): Promise<string> => {
    if (!featureFlags.threading) {
      return activeThreadId ?? `legacy-${userId}`;
    }
    if (activeThreadId) {
      return activeThreadId;
    }
    const created = await chatApi.createThread({
      user_id: userId,
      space_id: currentSpace?.space_id,
      title: input.slice(0, 60),
    });
    setThreads((prev) => [created, ...prev.filter((thread) => thread.id !== created.id)]);
    setActiveThreadId(created.id);
    return created.id;
  };

  const obsidianContextSources = useMemo<ContextSourceContract[]>(() => {
    if (!featureFlags.obsidianEventSync || !obsidianSession?.active_note_path) {
      return [];
    }
    const activeNote = {
      type: 'OBSIDIAN' as const,
      path: obsidianSession.active_note_path,
      extra: {
        source: 'active_note',
        session_id: obsidianSession.session_id,
        note_title: obsidianSession.active_note_title,
        selection: obsidianSession.active_selection,
        last_event_at: obsidianSession.last_event_at,
      },
    };
    const recentEvents = (obsidianSession.recent_events || [])
      .slice(-8)
      .map((event) => ({
        type: 'OBSIDIAN' as const,
        path: event.note_path || obsidianSession.active_note_path || '',
        extra: {
          source: 'obsidian_event',
          event_id: event.event_id,
          event_type: event.event_type,
          note_title: event.note_title,
          selection: event.selection,
          clicked_target: event.clicked_target,
          cursor_line: event.cursor_line,
          event_ts_ms: event.event_ts_ms,
        },
      }));
    return [activeNote, ...recentEvents];
  }, [obsidianSession]);

  const mergedContextSources = useMemo(
    () => [...pendingContextSources, ...obsidianContextSources],
    [pendingContextSources, obsidianContextSources]
  );

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;
    const threadId = await ensureThread();

    const userMessage = {
      id: Date.now().toString(),
      threadId,
      role: 'user' as const,
      content: input,
      timestamp: new Date(),
      metadata: {
        model: defaultModel,
        context_sources: mergedContextSources,
      },
    };
    addMessage(userMessage);
    const query = input;
    setInput('');
    setIsLoading(true);
    
    // Reset workflow state
    setWorkflowState({ stage: 'idle' });

    // Track current state for progressive updates
    let research = '';
    let plan = '';
    let answer = '';
    let metadata: Record<string, any> = {};
    let researchMessageId: string | null = null;
    let planMessageId: string | null = null;
    let answerMessageId: string | null = null;

    try {
      const request: ChatRequest = {
        user_id: userId,
        query: query,
        space_id: currentSpace?.space_id,
        model: defaultModel || currentSpace?.preferred_model,
        provider: defaultProvider,
        context_sources: mergedContextSources,
        thread_id: threadId,
      };

      // Use streaming with real-time callback
      await startStream(request, (event) => {
        // Process events as they arrive
        if (event.type === 'start') {
          setWorkflowState({ stage: 'research' });
        } else if (event.type === 'research' && event.content) {
          research = event.content;
          setWorkflowState((prev) => ({ ...prev, stage: 'research', research }));
          
          // Add or update research message
          if (!researchMessageId) {
            const msgId = `research-${Date.now()}`;
            researchMessageId = msgId;
            addMessage({
              id: msgId,
              threadId,
              role: 'research',
              content: research,
              timestamp: new Date(),
            });
          } else {
            updateMessage(threadId, researchMessageId, research);
          }
        } else if (event.type === 'plan' && event.content) {
          plan = event.content;
          setWorkflowState((prev) => ({ ...prev, stage: 'plan', research, plan }));
          
          if (!planMessageId) {
            const msgId = `plan-${Date.now()}`;
            planMessageId = msgId;
            addMessage({
              id: msgId,
              threadId,
              role: 'plan',
              content: plan,
              timestamp: new Date(),
            });
          } else {
            updateMessage(threadId, planMessageId, plan);
          }
        } else if (event.type === 'answer' && event.content) {
          answer = event.content;
          setWorkflowState((prev) => ({ ...prev, stage: 'implement', research, plan, answer, metadata }));
          
          if (!answerMessageId) {
            const msgId = `answer-${Date.now()}`;
            answerMessageId = msgId;
            addMessage({
              id: msgId,
              threadId,
              role: 'assistant',
              content: answer,
              timestamp: new Date(),
            });
          } else {
            updateMessage(threadId, answerMessageId, answer);
          }
        } else if (event.type === 'metadata' && event.data) {
          metadata = event.data;
          setWorkflowState((prev) => ({ ...prev, research, plan, answer, metadata }));
          if (answerMessageId) {
            updateMessage(threadId, answerMessageId, answer, metadata);
          }
        } else if (event.type === 'done') {
          setWorkflowState({ stage: 'complete', research, plan, answer, metadata });
        } else if (event.type === 'error') {
          addMessage({
            id: `error-${Date.now()}`,
            threadId,
            role: 'assistant',
            content: `Error: ${event.message || 'Unknown error'}`,
            timestamp: new Date(),
          });
        }
      });
    } catch (error) {
      console.error('Chat error:', error);
      addMessage({
        id: `error-${Date.now()}`,
        threadId,
        role: 'assistant',
        content: `Error: ${error instanceof Error ? error.message : 'Unknown error'}`,
        timestamp: new Date(),
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full min-h-0">
      {featureFlags.threading && (
        <div className="border-b border-gray-200 dark:border-gray-700 px-4 py-2">
          <div className="mb-2 flex items-center justify-between text-xs">
            <span
              className={
                obsidianSyncStatus === 'live'
                  ? 'text-emerald-600 dark:text-emerald-400'
                  : obsidianSyncStatus === 'error'
                    ? 'text-red-600 dark:text-red-400'
                    : 'text-gray-500 dark:text-gray-400'
              }
            >
              Obsidian sync: {obsidianSyncStatus}
            </span>
            {obsidianSession?.active_note_path && (
              <span className="truncate text-gray-600 dark:text-gray-300 max-w-[55%]">
                {obsidianSession.active_note_path}
              </span>
            )}
          </div>
          {obsidianSession && !obsidianSession.plugin_connected && obsidianSession.last_heartbeat_age_ms != null && (
            <div className="mb-2 text-[11px] text-amber-600 dark:text-amber-400">
              Plugin stale ({Math.round(obsidianSession.last_heartbeat_age_ms / 1000)}s since heartbeat)
            </div>
          )}
          {obsidianError && <div className="mb-2 text-xs text-red-600 dark:text-red-400">{obsidianError}</div>}
          {threadsError && (
            <div className="mb-2 text-xs text-red-600 dark:text-red-400 flex items-center justify-between">
              <span>{threadsError}</span>
              <button type="button" onClick={() => window.location.reload()} className="underline">
                Retry
              </button>
            </div>
          )}
          <div className="rounded-md border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/40 px-2 py-1 text-sm text-gray-600 dark:text-gray-300">
            {activeThreadId ? (
              <>Active thread: {threads.find((thread) => thread.id === activeThreadId)?.title ?? activeThreadId}</>
            ) : (
              <>Select a thread from the sidebar or send a message to create one.</>
            )}
          </div>
        </div>
      )}
      <div className="flex-1 overflow-y-auto p-4 min-h-0">
        {!activeThreadId && featureFlags.threading && !threadsLoading && (
          <div className="mb-4 rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-sm text-gray-600 dark:text-gray-300">
            Choose a thread or send a message to create one.
          </div>
        )}
        <MessageList messages={messages} />
        {(isLoading || isStreaming) && (
          <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400 mt-4" role="status" aria-live="polite">
            <div className="animate-spin rounded-full h-4 w-4 border-2 border-blue-500 border-t-transparent"></div>
            <span className="text-sm">
              {workflowState.stage === 'research' ? 'Researching...' :
               workflowState.stage === 'plan' ? 'Planning...' :
               workflowState.stage === 'implement' ? 'Implementing...' :
               'Processing...'}
            </span>
          </div>
        )}
      </div>
      <ChatInput
        value={input}
        onChange={setInput}
        onSend={handleSend}
        isLoading={isLoading || isStreaming}
      />
    </div>
  );
}
