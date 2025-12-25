export interface MeraAISettings {
	apiBaseUrl: string;
	userId: string;
	defaultModel: string;
	autoSaveConversations: boolean;
	conversationsFolder: string;
}

export const DEFAULT_SETTINGS: MeraAISettings = {
	apiBaseUrl: 'http://localhost:8000',
	userId: 'obsidian-user',
	defaultModel: 'openai/gpt-4o-mini',
	autoSaveConversations: true,
	conversationsFolder: 'Conversations'
}
