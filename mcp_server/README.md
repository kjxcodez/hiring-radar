# Hiring Radar MCP Server

Exposes key jobs search, company research, and application tracking capabilities as Model Context Protocol (MCP) JSON-RPC tools for LLMs.

## Exposed Tools

1. `search_jobs(sources: list[str], limit: int = 50) -> list[dict]`
   - Searches for open job postings directly from online platforms/ATS interfaces.
2. `get_company(name: str) -> dict | None`
   - Performs a case-insensitive substring search across the local database of discovered companies.
3. `list_applications() -> list[dict]`
   - Returns the list of currently tracked job applications and status transition logs.

## Setup & Testing

### Standalone execution

Start the server locally over standard input/output (stdio) transport:

```bash
.venv\Scripts\python.exe -m mcp_server.server
```

*(Note: Stdio transport uses stdin and stdout to process JSON-RPC messages. Do not print directly to stdout or run interactive commands in the terminal shell after launching.)*

### Client configuration

Full client setup configurations (e.g. for Claude Desktop) will be documented in later steps.
