import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface ChatRequest {
  user_id: string;
  query: string;
  model?: string;
  context_sources?: Array<{ type: string; value: string }>;
  space_id?: string;
}

export interface ChatResponse {
  user_id: string;
  answer: string;
  research?: string;
  plan?: string;
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

export const chatApi = {
  chat: async (request: ChatRequest): Promise<ChatResponse> => {
    const response = await apiClient.post<ChatResponse>('/chat', request);
    return response.data;
  },
  
  getSpaces: async (): Promise<Space[]> => {
    const response = await apiClient.get<Space[]>('/spaces');
    return response.data;
  },
  
  getSpace: async (spaceId: string): Promise<Space> => {
    const response = await apiClient.get<Space>(`/spaces/${spaceId}`);
    return response.data;
  },
  
  createSpace: async (space: {
    space_id: string;
    name: string;
    owner_id: string;
    monthly_token_budget?: number;
    monthly_api_calls?: number;
    preferred_model?: string;
  }): Promise<Space> => {
    const response = await apiClient.post<Space>('/spaces', space);
    return response.data;
  },
  
  getSpaceVisualization: async (spaceId: string, month?: string) => {
    const response = await apiClient.get(`/spaces/${spaceId}/visualization`, {
      params: { month },
    });
    return response.data;
  },
  
  getAgentActivity: async (sessionId: string) => {
    const response = await apiClient.get(`/workflow/${sessionId}/agents`);
    return response.data;
  },
};
