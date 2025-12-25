import { Plugin, Notice, Setting, App, PluginSettingTab } from 'obsidian';
import { MeraAISettings, DEFAULT_SETTINGS } from './settings';
import { MeraAIModal } from './modal';
import { MemoryManager } from './memory-manager';

export default class MeraAIPlugin extends Plugin {
	settings: MeraAISettings;
	memoryManager: MemoryManager;

	async onload() {
		await this.loadSettings();

		// Initialize memory manager
		this.memoryManager = new MemoryManager(this.settings);

		// Add ribbon icon for quick access
		this.addRibbonIcon('message-square', 'Mera AI Chat', (evt: MouseEvent) => {
			new MeraAIModal(this.app, this.settings, this.memoryManager).open();
		});

		// Add command palette commands
		this.addCommand({
			id: 'open-mera-ai-chat',
			name: 'Open Mera AI Chat',
			callback: () => {
				new MeraAIModal(this.app, this.settings, this.memoryManager).open();
			}
		});

		this.addCommand({
			id: 'add-memory',
			name: 'Add Current Note to Memory',
			callback: () => {
				const activeFile = this.app.workspace.getActiveFile();
				if (activeFile) {
					this.app.vault.read(activeFile).then(content => {
						this.memoryManager.addMemory(activeFile.basename, content);
						new Notice(`Added "${activeFile.basename}" to memory`);
					});
				} else {
					new Notice('No active note to add to memory');
				}
			}
		});

		this.addCommand({
			id: 'search-memories',
			name: 'Search Memories',
			callback: () => {
				// Open chat with search query prompt
				const modal = new MeraAIModal(this.app, this.settings, this.memoryManager);
				modal.setInitialQuery('Search my memories for: ');
				modal.open();
			}
		});

		// Add settings tab
		this.addSettingTab(new MeraAISettingTab(this.app, this));

		console.log('Mera AI plugin loaded');
	}

	onunload() {
		console.log('Mera AI plugin unloaded');
	}

	async loadSettings() {
		this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
	}

	async saveSettings() {
		await this.saveData(this.settings);
	}
}

class MeraAISettingTab extends PluginSettingTab {
	plugin: MeraAIPlugin;

	constructor(app: App, plugin: MeraAIPlugin) {
		super(app, plugin);
		this.plugin = plugin;
	}

	display(): void {
		const { containerEl } = this;

		containerEl.empty();

		containerEl.createEl('h2', { text: 'Mera AI Settings' });

		new Setting(containerEl)
			.setName('API Base URL')
			.setDesc('Base URL for Mera AI API (default: http://localhost:8000)')
			.addText(text => text
				.setPlaceholder('http://localhost:8000')
				.setValue(this.plugin.settings.apiBaseUrl)
				.onChange(async (value) => {
					this.plugin.settings.apiBaseUrl = value;
					await this.plugin.saveSettings();
				}));

		new Setting(containerEl)
			.setName('User ID')
			.setDesc('Your user ID for memory management (default: obsidian-user)')
			.addText(text => text
				.setPlaceholder('obsidian-user')
				.setValue(this.plugin.settings.userId)
				.onChange(async (value) => {
					this.plugin.settings.userId = value;
					await this.plugin.saveSettings();
				}));

		new Setting(containerEl)
			.setName('Default Model')
			.setDesc('Default LLM model to use (e.g., openai/gpt-4o-mini)')
			.addText(text => text
				.setPlaceholder('openai/gpt-4o-mini')
				.setValue(this.plugin.settings.defaultModel)
				.onChange(async (value) => {
					this.plugin.settings.defaultModel = value;
					await this.plugin.saveSettings();
				}));

		containerEl.createEl('h3', { text: 'Memory Settings' });

		new Setting(containerEl)
			.setName('Auto-save conversations')
			.setDesc('Automatically save chat conversations to notes')
			.addToggle(toggle => toggle
				.setValue(this.plugin.settings.autoSaveConversations)
				.onChange(async (value) => {
					this.plugin.settings.autoSaveConversations = value;
					await this.plugin.saveSettings();
				}));

		new Setting(containerEl)
			.setName('Conversations folder')
			.setDesc('Folder to save conversation notes (default: Conversations)')
			.addText(text => text
				.setPlaceholder('Conversations')
				.setValue(this.plugin.settings.conversationsFolder)
				.onChange(async (value) => {
					this.plugin.settings.conversationsFolder = value;
					await this.plugin.saveSettings();
				}));
	}
}
