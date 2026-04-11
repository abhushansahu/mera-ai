import axios from 'axios';
import { getRuntimeApiUrl, getRuntimeAuthToken, getRuntimeUserId, setRuntimeApiUrl } from '@/lib/config/runtime';
import {
  ContextSourceContract,
  FeatureFlagsContract,
  ObsidianContextEventContract,
  ObsidianContextSessionContract,
  SpaceContract,
} from '@/lib/types/contracts';

const API_URL = getRuntimeApiUrl();

export const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  config.baseURL = getRuntimeApiUrl();
  const headers = getRuntimeRequestHeaders();
  if (headers.Authorization) {
    config.headers.Authorization = headers.Authorization;
  }
  config.headers['X-User-Id'] = headers['X-User-Id'];
  return config;
});

export function getRuntimeRequestHeaders(): Record<string, string> {
  const authToken = getRuntimeAuthToken();
  return {
    ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
    'X-User-Id': getRuntimeUserId(),
  };
}

export function buildApiUrl(path: string): string {
  return `${getRuntimeApiUrl().replace(/\/+$/, '')}${path.startsWith('/') ? path : `/${path}`}`;
}

export function getConfiguredApiUrl(): string {
  return getRuntimeApiUrl();
}

export function setConfiguredApiUrl(url: string): void {
  setRuntimeApiUrl(url);
  apiClient.defaults.baseURL = getRuntimeApiUrl();
}

export interface ChatRequest {
  user_id?: string;
  query: string;
  model?: string;
  provider?: string;
  context_sources?: ContextSourceContract[];
  space_id?: string;
  thread_id?: string;
}

export interface ChatResponse {
  user_id: string;
  answer: string;
  research?: string;
  plan?: string;
  metadata?: Record<string, any>;
}

export type Space = SpaceContract;

export interface Thread {
  id: string;
  user_id: string;
  space_id?: string | null;
  title: string;
  archived: boolean;
  created_at: string;
  updated_at: string;
}

export interface PersistedMessage {
  id: string;
  user_id: string;
  thread_id: string;
  role: string;
  content: string;
  created_at: string;
  metadata: Record<string, any>;
}

export interface ProviderKeyStatus {
  owner_id: string;
  provider: string;
  key_version: string;
  last4: string;
  is_active: boolean;
  updated_at: string;
}

export interface SpaceUsage {
  space_id: string;
  month: string;
  tokens_used: number;
  api_calls_used: number;
  cost_usd: number;
  tokens_remaining: number;
}

export type FeatureFlagsResponse = FeatureFlagsContract;

export type ObsidianContextEventPayload = ObsidianContextEventContract;

export type ObsidianContextSession = ObsidianContextSessionContract;

export const chatApi = {
  chat: async (request: ChatRequest): Promise<ChatResponse> => {
    const response = await apiClient.post<ChatResponse>('/chat', request);
    return response.data;
  },
  
  getSpaces: async (): Promise<Space[]> => {
    const response = await apiClient.get<Space[]>('/spaces/list');
    return response.data;
  },
  
  getSpace: async (spaceId: string): Promise<Space> => {
    const response = await apiClient.get<Space>(`/spaces/${spaceId}`);
    return response.data;
  },
  
  createSpace: async (space: {
    space_id: string;
    name: string;
    owner_id?: string;
    monthly_token_budget?: number;
    monthly_api_calls?: number;
    preferred_model?: string;
  }): Promise<Space> => {
    const response = await apiClient.post<Space>('/spaces/create', space);
    return response.data;
  },
  
  getSpaceVisualization: async (spaceId: string, month?: string) => {
    const response = await apiClient.get(`/spaces/${spaceId}/visualization`, {
      params: { month },
    });
    return response.data;
  },

  getSpaceUsage: async (spaceId: string, month?: string): Promise<SpaceUsage> => {
    const response = await apiClient.get<SpaceUsage>(`/spaces/${spaceId}/usage`, { params: { month } });
    return response.data;
  },
  
  getAgentActivity: async (sessionId: string) => {
    const response = await apiClient.get(`/workflow/${sessionId}/agents`);
    return response.data;
  },

  createThread: async (payload: { user_id?: string; space_id?: string; title?: string }): Promise<Thread> => {
    const response = await apiClient.post<Thread>('/threads/create', payload);
    return response.data;
  },

  listThreads: async (payload: { user_id?: string; space_id?: string; include_archived?: boolean }): Promise<Thread[]> => {
    const response = await apiClient.get<Thread[]>('/threads/list', { params: payload });
    return response.data;
  },

  listThreadMessages: async (payload: { thread_id: string; user_id?: string }): Promise<PersistedMessage[]> => {
    const response = await apiClient.get<PersistedMessage[]>(`/threads/${payload.thread_id}/messages`, {
      params: { user_id: payload.user_id },
    });
    return response.data;
  },

  renameThread: async (payload: { thread_id: string; user_id?: string; title: string }): Promise<Thread> => {
    const response = await apiClient.post<Thread>(`/threads/${payload.thread_id}/rename`, {
      user_id: payload.user_id,
      title: payload.title,
    });
    return response.data;
  },

  archiveThread: async (payload: { thread_id: string; user_id?: string }): Promise<Thread> => {
    const response = await apiClient.post<Thread>(`/threads/${payload.thread_id}/archive`, null, {
      params: { user_id: payload.user_id },
    });
    return response.data;
  },

  saveProviderKey: async (payload: { owner_id?: string; provider: string; api_key: string }): Promise<ProviderKeyStatus> => {
    const response = await apiClient.post<ProviderKeyStatus>('/settings/providers/key', payload);
    return response.data;
  },

  getProviderKeyStatus: async (payload: { owner_id?: string; provider: string }): Promise<ProviderKeyStatus> => {
    const response = await apiClient.get<ProviderKeyStatus>('/settings/providers/key', { params: payload });
    return response.data;
  },

  linkThreadToObsidian: async (payload: { user_id?: string; thread_id: string; note_path: string; summary?: string }) => {
    const response = await apiClient.post('/obsidian/threads/link', payload);
    return response.data;
  },

  indexObsidian: async (prefixes: string[]) => {
    const response = await apiClient.post('/obsidian/index', { prefixes });
    return response.data;
  },

  ingestObsidianContextEvent: async (payload: {
    user_id?: string;
    space_id?: string;
    session_id?: string;
    event: ObsidianContextEventPayload;
  }) => {
    const response = await apiClient.post('/obsidian/context/events', payload);
    return response.data;
  },

  heartbeatObsidianContext: async (payload: {
    user_id?: string;
    space_id?: string;
    session_id?: string;
    active_note_path?: string;
    active_note_title?: string;
  }) => {
    const response = await apiClient.post('/obsidian/context/heartbeat', payload);
    return response.data;
  },

  getObsidianContextSession: async (payload: {
    user_id?: string;
    space_id?: string;
    session_id?: string;
  }): Promise<ObsidianContextSession> => {
    const response = await apiClient.get<ObsidianContextSession>('/obsidian/context/session', {
      params: payload,
    });
    return response.data;
  },

  getFeatureFlags: async (): Promise<FeatureFlagsResponse> => {
    const response = await apiClient.get<FeatureFlagsResponse>('/features');
    return response.data;
  },
};
