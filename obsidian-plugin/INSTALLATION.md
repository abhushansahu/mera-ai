# Mera AI Obsidian Plugin - Installation Guide

## Quick Installation

### Option 1: Manual Copy (Easiest)

1. **Build the plugin:**
   ```bash
   cd obsidian-plugin
   npm install
   npm run build
   ```

2. **Copy to Obsidian plugins folder:**
   
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

3. **Enable in Obsidian:**
   - Open Obsidian Settings → Community Plugins
   - Find "Mera AI" and toggle it ON
   - Configure settings (Settings → Mera AI)

### Option 2: Development Link (For Development)

1. **Build the plugin:**
   ```bash
   cd obsidian-plugin
   npm install
   npm run dev  # This watches for changes
   ```

2. **Create symbolic link:**
   
   **macOS/Linux:**
   ```bash
   ln -s $(pwd)/obsidian-plugin ~/.obsidian/plugins/mera-ai
   ```
   
   **Windows (PowerShell as Admin):**
   ```powershell
   New-Item -ItemType SymbolicLink -Path "$env:APPDATA\Obsidian\plugins\mera-ai" -Target "$(Get-Location)\obsidian-plugin"
   ```

3. **Reload Obsidian:**
   - Press `Ctrl+R` (or `Cmd+R` on Mac) to reload
   - Or restart Obsidian

## Verification

1. Check that the plugin appears in Settings → Community Plugins
2. Enable the plugin
3. You should see a message-square icon in the left ribbon
4. Click it to open the chat interface

## Troubleshooting

### Plugin not showing up
- Check that `main.js` exists in the plugin folder
- Check Obsidian console (Help → Toggle Developer Console) for errors
- Verify the folder structure matches: `plugins/mera-ai/main.js`

### Build errors
- Make sure Node.js is installed: `node --version`
- Install dependencies: `npm install`
- Check TypeScript version compatibility

### API connection errors
- Verify Mera AI is running: `curl http://localhost:8000/status`
- Check API Base URL in plugin settings matches your setup
- Ensure no firewall is blocking localhost connections
