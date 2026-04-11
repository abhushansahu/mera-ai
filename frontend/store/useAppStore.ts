import { create } from 'zustand';
import {
  ContextSourceContract,
  ObsidianContextEventContract,
  ObsidianContextSessionContract,
  SpaceContract,
} from '@/lib/types/contracts';

export interface Message {
  id: string;
  threadId: string;
  role: 'user' | 'assistant' | 'research' | 'plan';
  content: string;
  timestamp: Date;
  metadata?: Record<string, any>;
}

export type ContextSource = ContextSourceContract;
export type ObsidianContextEvent = ObsidianContextEventContract;
export type ObsidianSessionContext = ObsidianContextSessionContract;
export type Space = SpaceContract;

export interface WorkflowState {
  stage: 'idle' | 'research' | 'plan' | 'implement' | 'complete';
  research?: string;
  plan?: string;
  answer?: string;
  metadata?: Record<string, any>;
}

interface AppState {
  // Spaces
  currentSpace: Space | null;
  spaces: Space[];
  setCurrentSpace: (space: Space | null) => void;
  setSpaces: (spaces: Space[]) => void;
  
  // Messages
  messagesByThread: Record<string, Message[]>;
  activeThreadId: string | null;
  threads: Array<{
    id: string;
    title: string;
    archived: boolean;
    space_id?: string | null;
    updated_at: string;
  }>;
  defaultModel: string;
  defaultProvider: string;
  pendingContextSources: ContextSource[];
  rpiLayoutMode: 'compact' | 'expanded' | 'hidden';
  setRpiLayoutMode: (mode: 'compact' | 'expanded' | 'hidden') => void;
  setDefaultModel: (model: string) => void;
  setDefaultProvider: (provider: string) => void;
  setPendingContextSources: (sources: ContextSource[]) => void;
  obsidianSession: ObsidianSessionContext | null;
  obsidianSyncStatus: 'idle' | 'connecting' | 'live' | 'error';
  setObsidianSession: (session: ObsidianSessionContext | null) => void;
  setObsidianSyncStatus: (status: 'idle' | 'connecting' | 'live' | 'error') => void;
  setThreads: (
    threads:
      | Array<{ id: string; title: string; archived: boolean; space_id?: string | null; updated_at: string }>
      | ((prev: Array<{ id: string; title: string; archived: boolean; space_id?: string | null; updated_at: string }>) =>
          Array<{ id: string; title: string; archived: boolean; space_id?: string | null; updated_at: string }>)
  ) => void;
  setActiveThreadId: (threadId: string | null) => void;
  setThreadMessages: (threadId: string, messages: Message[]) => void;
  updateMessage: (threadId: string, messageId: string, content: string, metadata?: Record<string, any>) => void;
  addMessage: (message: Message) => void;
  clearMessages: () => void;
  
  // Workflow
  workflowState: WorkflowState;
  setWorkflowState: (state: WorkflowState | ((prev: WorkflowState) => WorkflowState)) => void;
  resetWorkflow: () => void;
  
  // Agent Activity
  agentActivity: Record<string, any>;
  setAgentActivity: (activity: Record<string, any>) => void;
}

export const useAppStore = create<AppState>()((set) => ({
  currentSpace: null,
  spaces: [],
  setCurrentSpace: (space) => set({ currentSpace: space }),
  setSpaces: (spaces) => set({ spaces }),
  
  messagesByThread: {},
  activeThreadId: null,
  threads: [],
  defaultModel: 'openai/gpt-4o-mini',
  defaultProvider: 'openrouter',
  pendingContextSources: [],
  rpiLayoutMode: 'compact',
  setRpiLayoutMode: (mode) => set({ rpiLayoutMode: mode }),
  setDefaultModel: (model) => set({ defaultModel: model }),
  setDefaultProvider: (provider) => set({ defaultProvider: provider }),
  setPendingContextSources: (sources) => set({ pendingContextSources: sources }),
  obsidianSession: null,
  obsidianSyncStatus: 'idle',
  setObsidianSession: (session) => set({ obsidianSession: session }),
  setObsidianSyncStatus: (status) => set({ obsidianSyncStatus: status }),
  setThreads: (threads) =>
    set((current) => ({
      threads: typeof threads === 'function' ? threads(current.threads) : threads,
    })),
  setActiveThreadId: (threadId) => set({ activeThreadId: threadId }),
  setThreadMessages: (threadId, messages) =>
    set((state) => ({ messagesByThread: { ...state.messagesByThread, [threadId]: messages } })),
  addMessage: (message) =>
    set((state) => {
      const existing = state.messagesByThread[message.threadId] ?? [];
      return {
        messagesByThread: {
          ...state.messagesByThread,
          [message.threadId]: [...existing, message],
        },
      };
    }),
  updateMessage: (threadId, messageId, content, metadata) =>
    set((state) => ({
      messagesByThread: {
        ...state.messagesByThread,
        [threadId]: (state.messagesByThread[threadId] ?? []).map((message) =>
          message.id === messageId
            ? { ...message, content, metadata: { ...(message.metadata ?? {}), ...(metadata ?? {}) } }
            : message
        ),
      },
    })),
  clearMessages: () =>
    set((state) => {
      if (!state.activeThreadId) {
        return {};
      }
      return {
        messagesByThread: {
          ...state.messagesByThread,
          [state.activeThreadId]: [],
        },
      };
    }),
  
  workflowState: { stage: 'idle' },
  setWorkflowState: (state) =>
    set((current) => ({
      workflowState: typeof state === 'function' ? state(current.workflowState) : state,
    })),
  resetWorkflow: () => set({ workflowState: { stage: 'idle' } }),
  
  agentActivity: {},
  setAgentActivity: (activity) => set({ agentActivity: activity }),
}));
