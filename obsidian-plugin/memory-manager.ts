import { MeraAISettings } from './settings';

export class MemoryManager {
	private settings: MeraAISettings;

	constructor(settings: MeraAISettings) {
		this.settings = settings;
	}

	async addMemory(title: string, content: string, metadata?: Record<string, any>): Promise<void> {
		try {
			const baseUrl = this.settings.apiBaseUrl.replace(/\/$/, ''); // Remove trailing slash
			const response = await fetch(`${baseUrl}/mem0/add`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: JSON.stringify({
					user_id: this.settings.userId,
					messages: content,
					metadata: {
						...metadata,
						source: 'obsidian',
						title: title,
					}
				}),
			});

			if (!response.ok) {
				const errorText = await response.text();
				throw new Error(`Failed to add memory: ${response.statusText} - ${errorText}`);
			}
		} catch (error) {
			console.error('Error adding memory:', error);
			throw error;
		}
	}

	async searchMemories(query: string, limit: number = 5): Promise<any[]> {
		try {
			const baseUrl = this.settings.apiBaseUrl.replace(/\/$/, ''); // Remove trailing slash
			const response = await fetch(`${baseUrl}/mem0/search`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: JSON.stringify({
					user_id: this.settings.userId,
					query: query,
					limit: limit,
				}),
			});

			if (!response.ok) {
				const errorText = await response.text();
				throw new Error(`Failed to search memories: ${response.statusText} - ${errorText}`);
			}

			const data = await response.json();
			return data.results || [];
		} catch (error) {
			console.error('Error searching memories:', error);
			return [];
		}
	}
}
