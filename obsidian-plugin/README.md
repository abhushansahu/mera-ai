# Mera AI Obsidian Plugin

Integrate Mera AI assistant directly into Obsidian. Chat with AI, manage memories, and enhance your notes without needing REST API calls.

## Features

- 💬 **Chat Interface**: Direct chat with Mera AI from Obsidian
- 🧠 **Memory Management**: Add notes to memory, search memories
- 📝 **Auto-save Conversations**: Automatically save chat conversations as notes
- 🔍 **Context-Aware**: Uses both your memories and Obsidian vault as context
- ⚡ **No REST API Required**: Direct integration, no need for Obsidian REST API plugin

## Installation

### Manual Installation

1. Copy the `obsidian-plugin` folder to your Obsidian vault's `.obsidian/plugins/` directory
2. Rename it to `mera-ai`
3. Open Obsidian Settings → Community Plugins
4. Enable "Mera AI" plugin

### Development Installation

1. Navigate to the plugin directory:
   ```bash
   cd obsidian-plugin
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Build the plugin:
   ```bash
   npm run build
   ```

4. Link to Obsidian:
   ```bash
   # On macOS
   ln -s $(pwd) ~/.obsidian/plugins/mera-ai
   
   # On Linux
   ln -s $(pwd) ~/.config/obsidian/plugins/mera-ai
   
   # On Windows (PowerShell)
   New-Item -ItemType SymbolicLink -Path "$env:APPDATA\Obsidian\plugins\mera-ai" -Target (Get-Location)
   ```

## Configuration

1. Open Obsidian Settings → Mera AI
2. Configure:
   - **API Base URL**: `http://localhost:8000` (default)
   - **User ID**: Your user ID for memory management
   - **Default Model**: LLM model to use (e.g., `openai/gpt-4o-mini`)
   - **Auto-save conversations**: Enable to automatically save chats as notes
   - **Conversations folder**: Folder to save conversation notes

## Usage

### Open Chat

- Click the ribbon icon (message-square icon)
- Or use Command Palette: "Mera AI: Open Mera AI Chat"
- Or use hotkey (if configured)

### Commands

- **Open Mera AI Chat**: Open the chat interface
- **Add Current Note to Memory**: Add the active note to your memory
- **Search Memories**: Search your memories from Obsidian

### Chat Features

- Type your query and press Enter (Shift+Enter for new line)
- The AI will use both your memories and Obsidian vault as context
- Responses are formatted with markdown support
- Conversations can be auto-saved as notes

### Memory Management

- Add notes to memory using the command or from chat
- Search memories directly from Obsidian
- All memories are stored in your Mem0 instance

## API Endpoints Used

The plugin communicates with your local Mera AI API:

- `POST /chat` - Send chat messages
- `POST /mem0/add` - Add memories (via MemoryManager)
- `POST /mem0/search` - Search memories (via MemoryManager)

## Requirements

- Mera AI API running on `http://localhost:8000` (or configured URL)
- Mem0 service running on `http://localhost:8001`
- Obsidian installed and running

## Development

```bash
# Watch mode (auto-rebuild on changes)
npm run dev

# Production build
npm run build
```

## Troubleshooting

### Plugin not loading
- Check that `main.js` exists in the plugin folder
- Check Obsidian console for errors (Help → Toggle Developer Console)

### API connection errors
- Verify Mera AI API is running: `curl http://localhost:8000/status`
- Check API Base URL in plugin settings
- Ensure no firewall is blocking localhost connections

### Memory operations failing
- Verify Mem0 service is running: `curl http://localhost:8001/health`
- Check user ID in plugin settings matches your setup

## License

MIT
