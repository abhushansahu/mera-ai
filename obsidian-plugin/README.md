# Mera AI Obsidian Plugin

Chat with Mera AI directly from Obsidian. Manage memories and save conversations as notes.

## Installation

1. Build the plugin:
   ```bash
   cd obsidian-plugin
   npm install
   npm run build
   ```

2. Copy to Obsidian plugins folder:
   ```bash
   # macOS
   cp -r obsidian-plugin ~/.obsidian/plugins/mera-ai
   
   # Linux
   cp -r obsidian-plugin ~/.config/obsidian/plugins/mera-ai
   
   # Windows
   Copy-Item -Recurse obsidian-plugin "$env:APPDATA\Obsidian\plugins\mera-ai"
   ```

3. Enable in Obsidian: Settings → Community Plugins → Enable "Mera AI"

## Configuration

Open Obsidian Settings → Mera AI and set:
- **API Base URL**: `http://localhost:8000` (default)
- **User ID**: Your user ID for memory
- **Default Model**: AI model to use (e.g., `openai/gpt-4o-mini`)

## Usage

- Click the ribbon icon to open chat
- Or use Command Palette: "Mera AI: Open Mera AI Chat"
- Type your question and press Enter
- Conversations can be auto-saved as notes

## Commands

- **Open Mera AI Chat**: Open chat interface
- **Add Current Note to Memory**: Save active note to memory
- **Search Memories**: Search your memories

## Requirements

- Mera AI API running on `http://localhost:8000`
- Mem0 service running on `http://localhost:8001`

## Troubleshooting

**Plugin not loading?**
- Check `main.js` exists in plugin folder
- Check Obsidian console (Help → Toggle Developer Console)

**API connection errors?**
- Verify API is running: `curl http://localhost:8000/status`
- Check API Base URL in settings

**Memory operations failing?**
- Verify Mem0 is running: `curl http://localhost:8001/health`
- Check user ID matches your setup
