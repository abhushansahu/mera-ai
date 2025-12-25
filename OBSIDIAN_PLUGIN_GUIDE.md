# Obsidian Plugin Integration Guide

## Overview

The Mera AI Obsidian plugin allows you to interact with your AI assistant directly from Obsidian, eliminating the need for REST API calls to Obsidian. The plugin communicates directly with your Mera AI API.

## Benefits

✅ **No REST API Required**: Direct integration, no need for Obsidian REST API plugin  
✅ **Native Obsidian Experience**: Chat with AI directly in Obsidian  
✅ **Memory Management**: Add notes to memory, search memories from Obsidian  
✅ **Auto-save Conversations**: Automatically save chat conversations as notes  
✅ **Context-Aware**: Uses both your memories and Obsidian vault as context  

## Installation

### Step 1: Build the Plugin

```bash
cd obsidian-plugin
npm install
npm run build
```

This creates `main.js` and `main.js.map` files needed by Obsidian.

### Step 2: Install in Obsidian

**Option A: Manual Copy**

1. Copy the entire `obsidian-plugin` folder to your Obsidian plugins directory:
   
   **macOS:**
   ```bash
   cp -r obsidian-plugin ~/.obsidian/plugins/mera-ai
   ```
   
   **Linux:**
   ```bash
   cp -r obsidian-plugin ~/.config/obsidian/plugins/mera-ai
   ```
   
   **Windows:**
   ```powershell
   Copy-Item -Recurse obsidian-plugin "$env:APPDATA\Obsidian\plugins\mera-ai"
   ```

2. Restart Obsidian or reload plugins (Ctrl+R / Cmd+R)

**Option B: Development Link (Recommended for Development)**

1. Create a symbolic link:
   
   **macOS/Linux:**
   ```bash
   ln -s $(pwd)/obsidian-plugin ~/.obsidian/plugins/mera-ai
   ```
   
   **Windows (PowerShell as Admin):**
   ```powershell
   New-Item -ItemType SymbolicLink -Path "$env:APPDATA\Obsidian\plugins\mera-ai" -Target "$(Get-Location)\obsidian-plugin"
   ```

2. Use `npm run dev` for watch mode (auto-rebuilds on changes)

### Step 3: Enable Plugin

1. Open Obsidian Settings → Community Plugins
2. Find "Mera AI" in the list
3. Toggle it ON
4. Configure settings (Settings → Mera AI)

## Configuration

Open **Settings → Mera AI** and configure:

- **API Base URL**: `http://localhost:8000` (default - matches your Mera AI API)
- **User ID**: Your user ID for memory management (default: `obsidian-user`)
- **Default Model**: LLM model to use (e.g., `openai/gpt-4o-mini`)
- **Auto-save conversations**: Enable to save chats as notes
- **Conversations folder**: Folder name for saved conversations (default: `Conversations`)

## Usage

### Opening the Chat

**Method 1: Ribbon Icon**
- Click the message-square icon in the left ribbon

**Method 2: Command Palette**
- Press `Ctrl+P` (or `Cmd+P` on Mac)
- Type "Mera AI: Open Mera AI Chat"
- Press Enter

**Method 3: Hotkey** (if configured)
- Set up a custom hotkey in Settings → Hotkeys

### Chat Interface

1. **Type your query** in the input box
2. **Press Enter** to send (Shift+Enter for new line)
3. **View response** in the response area below
4. **Use buttons**:
   - **Send**: Send your message
   - **Search Memories**: Search your memory database
   - **Clear**: Clear the response area

### Commands

Available via Command Palette (`Ctrl+P` / `Cmd+P`):

- **Mera AI: Open Mera AI Chat** - Open the chat interface
- **Mera AI: Add Current Note to Memory** - Add the active note to your memory
- **Mera AI: Search Memories** - Open chat with memory search prompt

### Features

#### 1. Chat with AI
- Ask questions, get answers
- AI uses your memories and Obsidian vault as context
- Responses are formatted with markdown support

#### 2. Memory Management
- Add notes to memory directly from Obsidian
- Search your memories
- All memories stored in your Mem0 instance

#### 3. Auto-save Conversations
- When enabled, conversations are automatically saved as notes
- Saved in the configured "Conversations" folder
- Format: `YYYY-MM-DDTHH-MM-SS_conversation.md`

## How It Works

### Architecture

```
Obsidian Plugin → Mera AI API (localhost:8000) → Mem0 Service (localhost:8001)
                                      ↓
                              Unified Orchestrator
                                      ↓
                    ┌─────────────────┴─────────────────┐
                    ↓                                   ↓
            Memory (Mem0)                    Obsidian Vault (via plugin)
```

### API Endpoints Used

The plugin communicates with your Mera AI API:

- `POST /chat` - Send chat messages
- `POST /mem0/add` - Add memories
- `POST /mem0/search` - Search memories
- `GET /mem0/get_all/{user_id}` - Get all memories

### No REST API Needed

Unlike the previous setup that required:
- Obsidian REST API plugin
- REST API token configuration
- HTTP calls from Python to Obsidian

The new plugin:
- ✅ Runs directly in Obsidian
- ✅ Makes HTTP calls to your Mera AI API
- ✅ Uses Obsidian's native API to read/write notes
- ✅ No external REST API plugin needed

## Development

### Watch Mode (Auto-rebuild)

```bash
cd obsidian-plugin
npm run dev
```

This watches for file changes and automatically rebuilds.

### Production Build

```bash
npm run build
```

### File Structure

```
obsidian-plugin/
├── main.ts              # Main plugin entry point
├── settings.ts          # Settings interface
├── modal.ts             # Chat modal UI
├── memory-manager.ts    # Memory operations
├── manifest.json        # Plugin manifest
├── package.json         # Dependencies
├── tsconfig.json        # TypeScript config
├── esbuild.config.mjs   # Build configuration
└── README.md            # Plugin documentation
```

## Troubleshooting

### Plugin Not Loading

1. **Check main.js exists:**
   ```bash
   ls ~/.obsidian/plugins/mera-ai/main.js
   ```

2. **Check Obsidian console:**
   - Help → Toggle Developer Console
   - Look for errors

3. **Verify build:**
   ```bash
   cd obsidian-plugin
   npm run build
   ```

### API Connection Errors

1. **Verify Mera AI is running:**
   ```bash
   curl http://localhost:8000/status
   ```

2. **Check API Base URL in settings:**
   - Should be `http://localhost:8000`
   - No trailing slash

3. **Check firewall:**
   - Ensure localhost connections are allowed

### Memory Operations Failing

1. **Verify Mem0 is running:**
   ```bash
   curl http://localhost:8001/health
   ```

2. **Check user ID:**
   - Should match your setup
   - Default: `obsidian-user`

3. **Check API logs:**
   ```bash
   # Check main app logs if running
   # Or check Mem0 container logs
   docker logs mera-ai-mem0
   ```

## Comparison: Old vs New

### Old Setup (REST API)
```
Python App → HTTP → Obsidian REST API Plugin → Obsidian Vault
```
- Required Obsidian REST API plugin
- Required REST API token
- One-way communication (Python → Obsidian)

### New Setup (Native Plugin)
```
Obsidian Plugin → HTTP → Mera AI API → Mem0
Obsidian Plugin → Native API → Obsidian Vault
```
- No REST API plugin needed
- No REST API token needed
- Bi-directional (Obsidian ↔ Mera AI)
- Native Obsidian experience

## Next Steps

1. **Build and install the plugin** (see Installation above)
2. **Configure settings** in Obsidian
3. **Start using it!** Click the ribbon icon to chat
4. **Add notes to memory** using the command
5. **Search memories** directly from Obsidian

Enjoy your integrated AI assistant! 🚀
