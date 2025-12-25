import { App, Modal, Setting, TextAreaComponent, ButtonComponent } from 'obsidian';
import { MeraAISettings } from './settings';
import { MemoryManager } from './memory-manager';

export class MeraAIModal extends Modal {
	private settings: MeraAISettings;
	private memoryManager: MemoryManager;
	private queryInput: TextAreaComponent;
	private responseArea: HTMLElement;
	private initialQuery: string = '';

	constructor(app: App, settings: MeraAISettings, memoryManager: MemoryManager) {
		super(app);
		this.settings = settings;
		this.memoryManager = memoryManager;
	}

	setInitialQuery(query: string) {
		this.initialQuery = query;
	}

	onOpen() {
		const { contentEl } = this;
		contentEl.empty();

		contentEl.createEl('h2', { text: 'Mera AI Chat' });

		// Query input area
		const queryContainer = contentEl.createDiv('mera-ai-query-container');
		this.queryInput = new TextAreaComponent(queryContainer);
		this.queryInput.setPlaceholder('Ask me anything...');
		this.queryInput.setValue(this.initialQuery);
		this.queryInput.inputEl.setAttribute('rows', '3');
		this.queryInput.inputEl.style.width = '100%';
		this.queryInput.inputEl.style.minHeight = '80px';

		// Response area
		const responseContainer = contentEl.createDiv('mera-ai-response-container');
		responseContainer.style.marginTop = '20px';
		responseContainer.style.padding = '15px';
		responseContainer.style.border = '1px solid var(--background-modifier-border)';
		responseContainer.style.borderRadius = '4px';
		responseContainer.style.minHeight = '200px';
		responseContainer.style.maxHeight = '400px';
		responseContainer.style.overflowY = 'auto';
		responseContainer.createEl('p', { 
			text: 'Response will appear here...',
			attr: { style: 'color: var(--text-muted);' }
		});
		this.responseArea = responseContainer;

		// Button container
		const buttonContainer = contentEl.createDiv('mera-ai-button-container');
		buttonContainer.style.marginTop = '15px';
		buttonContainer.style.display = 'flex';
		buttonContainer.style.gap = '10px';

		// Send button
		const sendButton = new ButtonComponent(buttonContainer)
			.setButtonText('Send')
			.setCta()
			.onClick(() => this.sendMessage());

		// Search memories button
		const searchButton = new ButtonComponent(buttonContainer)
			.setButtonText('Search Memories')
			.onClick(() => this.searchMemories());

		// Clear button
		const clearButton = new ButtonComponent(buttonContainer)
			.setButtonText('Clear')
			.onClick(() => this.clearResponse());

		// Allow Enter to send (Shift+Enter for new line)
		this.queryInput.inputEl.addEventListener('keydown', (evt: KeyboardEvent) => {
			if (evt.key === 'Enter' && !evt.shiftKey) {
				evt.preventDefault();
				this.sendMessage();
			}
		});
	}

	onClose() {
		const { contentEl } = this;
		contentEl.empty();
	}

	private async sendMessage() {
		const query = this.queryInput.getValue().trim();
		if (!query) {
			return;
		}

		// Show loading state
		this.responseArea.empty();
		this.responseArea.createEl('p', { 
			text: 'Thinking...',
			attr: { style: 'color: var(--text-muted); font-style: italic;' }
		});

		try {
			const response = await fetch(`${this.settings.apiBaseUrl}/chat`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: JSON.stringify({
					user_id: this.settings.userId,
					query: query,
					model: this.settings.defaultModel,
					context_sources: ['MEMORY', 'OBSIDIAN'] // Use both memory and Obsidian vault
				}),
			});

			if (!response.ok) {
				throw new Error(`API error: ${response.statusText}`);
			}

			const data = await response.json();
			
			// Display response
			this.responseArea.empty();
			const responseText = this.responseArea.createEl('div');
			responseText.innerHTML = this.formatResponse(data.answer);

			// Auto-save conversation if enabled
			if (this.settings.autoSaveConversations) {
				await this.saveConversation(query, data.answer);
			}

		} catch (error) {
			this.responseArea.empty();
			this.responseArea.createEl('p', { 
				text: `Error: ${error.message}`,
				attr: { style: 'color: var(--text-error);' }
			});
			console.error('Error sending message:', error);
		}
	}

	private async searchMemories() {
		const query = this.queryInput.getValue().trim() || 'recent memories';
		
		this.responseArea.empty();
		this.responseArea.createEl('p', { 
			text: 'Searching memories...',
			attr: { style: 'color: var(--text-muted); font-style: italic;' }
		});

		try {
			const memories = await this.memoryManager.searchMemories(query, 10);
			
			this.responseArea.empty();
			if (memories.length === 0) {
				this.responseArea.createEl('p', { 
					text: 'No memories found.',
					attr: { style: 'color: var(--text-muted);' }
				});
			} else {
				const list = this.responseArea.createEl('ul');
				memories.forEach((memory: any) => {
					const item = list.createEl('li');
					item.createEl('strong', { text: memory.metadata?.title || 'Memory' });
					item.createEl('br');
					item.createEl('span', { 
						text: memory.memory || memory.text || JSON.stringify(memory),
						attr: { style: 'font-size: 0.9em; color: var(--text-muted);' }
					});
				});
			}
		} catch (error) {
			this.responseArea.empty();
			this.responseArea.createEl('p', { 
				text: `Error searching memories: ${error.message}`,
				attr: { style: 'color: var(--text-error);' }
			});
		}
	}

	private clearResponse() {
		this.responseArea.empty();
		this.responseArea.createEl('p', { 
			text: 'Response will appear here...',
			attr: { style: 'color: var(--text-muted);' }
		});
		this.queryInput.setValue('');
	}

	private formatResponse(text: string): string {
		// Convert markdown to HTML for better display
		// Simple markdown formatting
		return text
			.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
			.replace(/\*(.+?)\*/g, '<em>$1</em>')
			.replace(/`(.+?)`/g, '<code>$1</code>')
			.replace(/\n/g, '<br>');
	}

	private async saveConversation(query: string, answer: string) {
		try {
			const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
			const filename = `${this.settings.conversationsFolder}/${timestamp}_conversation.md`;
			
			const content = `# Conversation - ${new Date().toLocaleString()}

## Query
${query}

## Response
${answer}

---
*Generated by Mera AI*
`;

			// Ensure folder exists
			const folder = this.app.vault.getAbstractFileByPath(this.settings.conversationsFolder);
			if (!folder) {
				await this.app.vault.createFolder(this.settings.conversationsFolder);
			}

			await this.app.vault.create(filename, content);
		} catch (error) {
			console.error('Error saving conversation:', error);
		}
	}
}
