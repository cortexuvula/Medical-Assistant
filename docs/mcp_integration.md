# MCP (Model Context Protocol) Integration

The Medical Assistant now supports MCP tools, allowing the chat agent to access external services and capabilities through a standardized protocol.

## What is MCP?

MCP (Model Context Protocol) is a standard protocol that enables LLMs to interact with external tools and services. MCP servers expose capabilities like web search, file access, API integrations, and more.

## Features

- **Dynamic Tool Discovery**: Automatically discovers available tools from MCP servers
- **Easy Configuration**: Add new tools via JSON configuration without code changes
- **Visual Integration**: Clear indicators in chat when MCP tools are used
- **Secure Execution**: Subprocess isolation and API key encryption
- **Hot Reload**: Add or remove MCP servers without restarting the app

## Configuration

### Via UI

1. Click the **"MCP Tools"** button in the Chat tab
2. Use the dialog to:
   - Add new MCP servers
   - Import JSON configurations
   - Test connections
   - Enable/disable servers

### Via JSON Import

Paste a configuration like this in the Import tab:

```json
{
  "mcpServers": {
    "brave-search": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-brave-search"],
      "env": {"BRAVE_API_KEY": "YOUR_API_KEY"}
    }
  }
}
```

## Available MCP Servers

### Official Servers

1. **Brave Search** - Web search capabilities
   ```bash
   npx -y @modelcontextprotocol/server-brave-search
   ```
   Required: `BRAVE_API_KEY` environment variable
   
   **Rate Limits:**
   - 1 request per second
   - 2,000 requests per month (free tier)
   - Get your API key at: https://brave.com/search/api/

2. **File System** - Local file access
   ```bash
   npx -y @modelcontextprotocol/server-filesystem /path/to/directory
   ```
   
3. **GitHub** - Repository access
   ```bash
   npx -y @modelcontextprotocol/server-github
   ```
   Required: `GITHUB_PERSONAL_ACCESS_TOKEN`

4. **Google Maps** - Location and mapping
   ```bash
   npx -y @modelcontextprotocol/server-googlemaps
   ```
   Required: `GOOGLE_MAPS_API_KEY`

### Medical-Specific Servers

Custom MCP servers can be created for medical use cases:

- Drug interaction databases
- Medical reference APIs
- Lab result analyzers
- Clinical guideline repositories

## Usage Examples

Once configured, you can use MCP tools naturally in chat:

**Web Search:**
```
"Search for the latest COVID-19 treatment guidelines from the CDC"
```

**File Operations:**
```
"Read the patient notes from today's appointments"
```

**Medical Queries:**
```
"Check drug interactions between metformin and lisinopril"
```

## Security Considerations

1. **API Keys**: Stored encrypted in application settings
2. **Process Isolation**: Each MCP server runs in a separate process
3. **Permission Control**: File system access requires explicit directory permissions
4. **Confirmation**: Destructive operations require user confirmation

## Rate Limiting

The Medical Assistant automatically enforces rate limits for known MCP servers:

- **Brave Search**: Automatically enforces 1 request per second limit
  - The system will wait if requests are made too quickly
  - Prevents 429 (Too Many Requests) errors
  - Each tool within a server is rate-limited independently

## Troubleshooting

### Server Won't Start
- Check that Node.js and npm are installed
- Verify the command works in terminal: `npx -y @modelcontextprotocol/server-name`
- Check API keys are set correctly

### Tools Not Appearing
- Ensure "Enable Tools" is checked in the chat interface
- Check server status in MCP configuration dialog
- Review application logs for errors

### Connection Timeout
- Some servers take time to initialize on first run
- Try testing the connection again after a few seconds
- Check firewall/antivirus isn't blocking the subprocess
- Verify your API key is valid (for Brave Search, get a key from https://brave.com/search/api/)

### Tool Execution Issues
- The AI needs to properly format tool calls in `<tool_call>` blocks
- GPT-4 or Claude models work better for tool calling than GPT-3.5
- Check the logs for detailed error messages
- Some MCP servers may have rate limits or require specific parameters
- If you see process termination errors, check that your API keys are valid
- The application will show stderr output from MCP servers in the logs
- Rate limit errors (429) indicate you've exceeded the API's request limits
- For Brave Search: respect the 1 req/sec limit and 2,000 req/month quota

## Creating Custom MCP Servers

MCP servers communicate via JSON-RPC 2.0 over stdio. Basic structure:

```python
#!/usr/bin/env python3
import json
import sys

def handle_request(request):
    method = request.get("method")
    
    if method == "initialize":
        return {"protocolVersion": "1.0", "capabilities": {}}
    
    elif method == "tools/list":
        return {
            "tools": [{
                "name": "my_tool",
                "description": "Description of my tool",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    }
                }
            }]
        }
    
    elif method == "tools/call":
        # Handle tool execution
        params = request.get("params", {})
        tool_name = params.get("name")
        args = params.get("arguments", {})
        
        # Your tool logic here
        result = {"output": "Tool result"}
        
        return {"content": [{"type": "text", "text": str(result)}]}

# Main loop
while True:
    line = sys.stdin.readline()
    if not line:
        break
    
    request = json.loads(line)
    response = {
        "jsonrpc": "2.0",
        "id": request.get("id"),
        "result": handle_request(request)
    }
    
    print(json.dumps(response))
    sys.stdout.flush()
```

## Best Practices

1. **Minimize Active Servers**: Only enable servers you actively use
2. **Secure API Keys**: Use environment variables, never hardcode
3. **Test First**: Use the test connection feature before saving
4. **Monitor Resources**: MCP servers run as subprocesses
5. **Regular Updates**: Keep MCP server packages updated

## Future Enhancements

- Automatic server discovery from npm registry
- Built-in medical MCP servers
- Tool usage analytics
- Batch tool operations
- Async tool execution with progress tracking