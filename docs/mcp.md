# Model Context Protocol (MCP) Client Connection Guide

This guide explains how to connect the **Hiring Radar** MCP server to common AI assistants and IDE extensions.

---

## 1. Claude Desktop

Claude Desktop runs MCP servers locally via standard input/output (stdio) streams.

### Configuration File Locations
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

### Copy-pasteable Configuration
Add the following entry to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "hiring-radar": {
      "command": "C:\\Users\\91637\\Desktop\\Business Project\\hiring-radar\\.venv\\Scripts\\python.exe",
      "args": ["-m", "mcp_server.server"],
      "cwd": "C:\\Users\\91637\\Desktop\\Business Project\\hiring-radar"
    }
  }
}
```

*Note: Double backslashes `\\` are required on Windows to escape path characters. Replace the paths above if your installation directory differs.*

### Troubleshooting
> [!TIP]
> If tools do not appear in your conversation composer, **fully close and restart the Claude Desktop app** (from the tray menu or System tray, not just by reloading the window).

---

## 2. Cursor

Cursor supports custom MCP server configurations globally or on a per-project basis.

### Configuration Methods

#### Via Settings UI (Recommended)
1. Go to **Settings** -> **Features** -> **MCP**.
2. Click **+ Add New MCP Server**.
3. Fill in the parameters:
   - **Name:** `hiring-radar`
   - **Type:** `command`
   - **Command:** `C:\Users\91637\Desktop\Business Project\hiring-radar\.venv\Scripts\python.exe -m mcp_server.server`

#### Via Config File
- **Global Config Path:** `%USERPROFILE%\.cursor\mcp.json` (Windows) or `~/.cursor/mcp.json` (macOS/Linux)
- **Project Config Path:** `.cursor/mcp.json` at the root of the project.

```json
{
  "mcpServers": {
    "hiring-radar": {
      "command": "C:\\Users\\91637\\Desktop\\Business Project\\hiring-radar\\.venv\\Scripts\\python.exe",
      "args": ["-m", "mcp_server.server"],
      "cwd": "C:\\Users\\91637\\Desktop\\Business Project\\hiring-radar"
    }
  }
}
```

### Troubleshooting
> [!TIP]
> If tools fail to show, toggle the server off and back on in Cursor's settings UI, or restart the editor.

---

## 3. VS Code (Cline / Roo Code)

 Cline and Roo Code support standard `mcpServers` JSON structures in their global settings.

### Configuration File Locations
- **Windows:** `%APPDATA%\Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json`
- **macOS:** `~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`

### Copy-pasteable Configuration
```json
{
  "mcpServers": {
    "hiring-radar": {
      "command": "C:\\Users\\91637\\Desktop\\Business Project\\hiring-radar\\.venv\\Scripts\\python.exe",
      "args": ["-m", "mcp_server.server"],
      "cwd": "C:\\Users\\91637\\Desktop\\Business Project\\hiring-radar"
    }
  }
}
```

### Troubleshooting
> [!TIP]
> Open the VS Code Developer Tools console (**Help** -> **Toggle Developer Tools**) to view connection outputs or check for error traces if connection fails.

---

## 4. ChatGPT

ChatGPT runs in the cloud and cannot connect directly to local stdio processes on your computer. It connects to servers using the **SSE (Server-Sent Events)** network transport.

### Connection Workflow

1. **Start the local server in HTTP/SSE transport mode**:
   ```bash
   .venv\Scripts\python.exe -m app.cli mcp-serve --transport sse --port 8811
   ```

2. **Expose the local port to the public internet** (using `ngrok`):
   ```bash
   ngrok http 8811
   ```
   Copy the generated public HTTPS URL (e.g., `https://xxxx.ngrok-free.app`).

3. **Configure ChatGPT**:
   - Enable **Developer Mode** under *Settings* -> *Apps & Connectors*.
   - Click **Add Custom Connector**.
   - Input the public URL: `https://xxxx.ngrok-free.app/mcp` (or `/sse` depending on client configuration settings).
   - Once ChatGPT discovers the tools, save the connector.

### Troubleshooting
> [!TIP]
> Ensure the ngrok tunnel window remains open and active. ChatGPT will fail to invoke tools if the tunnel is closed.

---

## 5. Testing without a GUI Client

You can run the MCP SDK's built-in developer/inspector tool to verify the server standalone:

```bash
npx @modelcontextprotocol/inspector .venv\Scripts\python.exe -m mcp_server.server
```

This launches a web-based testing utility in your default browser. You can inspect active tools, read URIs, render templates, and trigger test payloads manually.
