import { create } from 'zustand';

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'research' | 'plan';
  content: string;
  timestamp: Date;
  metadata?: Record<string, any>;
}

export interface Space {
  space_id: string;
  name: string;
  owner_id: string;
  status: string;
  monthly_token_budget: number;
  monthly_api_calls: number;
  preferred_model: string;
}

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
  messages: Message[];
  addMessage: (message: Message) => void;
  clearMessages: () => void;
  
  // Workflow
  workflowState: WorkflowState;
  setWorkflowState: (state: WorkflowState) => void;
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
  
  messages: [],
  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  clearMessages: () => set({ messages: [] }),
  
  workflowState: { stage: 'idle' },
  setWorkflowState: (state) => set({ workflowState: state }),
  resetWorkflow: () => set({ workflowState: { stage: 'idle' } }),
  
  agentActivity: {},
  setAgentActivity: (activity) => set({ agentActivity: activity }),
}));
