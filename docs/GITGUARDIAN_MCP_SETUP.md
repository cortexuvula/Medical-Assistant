# GitGuardian MCP Server Setup

**Status**: ✅ Configured in `.mcp.json`

---

## Overview

The GitGuardian MCP (Model Context Protocol) Server brings AI-assisted secrets security directly into your development workflow. It enables real-time detection and remediation of hardcoded credentials, API keys, and other sensitive data.

---

## Features

### 🔍 Secret Detection
- **500+ Secret Detectors**: Industry-leading detection for API keys, passwords, tokens, and certificates
- **Real-Time Scanning**: Scan code as you write to prevent credential leaks
- **Multi-Language Support**: Works across all programming languages

### 🛡️ Incident Management
- **Acknowledge Incidents**: Mark secrets as false positives or resolved
- **Remediation Actions**: Automated multi-step fixes (remove hardcoded secrets, create `.env.example` files)
- **Honeytoken Injection**: Create and manage honeytokens for security monitoring

### 🔒 Security by Design
- **Read-Only Permissions**: Minimizes security risk
- **Auditable Actions**: All agent behavior is logged and supervised
- **OAuth Authentication**: Secure token-based authentication with browser flow

---

## Configuration

The GitGuardian MCP server has been added to `.mcp.json`:

```json
{
  "mcpServers": {
    "gitguardian": {
      "command": "/home/cortexuvula/.local/bin/uvx",
      "args": [
        "--from",
        "git+https://github.com/GitGuardian/ggmcp.git",
        "developer-mcp-server"
      ],
      "env": {
        "GITGUARDIAN_URL": "https://dashboard.gitguardian.com",
        "ENABLE_LOCAL_OAUTH": "true"
      }
    }
  }
}
```

---

## Authentication

### Option 1: OAuth (Default - Recommended)

**Current Configuration**: ✅ Enabled

When you first use the GitGuardian MCP server:
1. A browser window will open automatically
2. Sign in to your GitGuardian account
3. Authorize the MCP server
4. Tokens are stored securely in `~/.gitguardian/`

**No manual configuration needed!**

---

### Option 2: Personal Access Token (Alternative)

If you prefer to use a Personal Access Token instead of OAuth:

1. **Get Your PAT**:
   - Visit: https://dashboard.gitguardian.com/api/personal-access-tokens
   - Click "Create token"
   - Copy the token

2. **Update `.mcp.json`**:
   ```json
   "gitguardian": {
     "command": "/home/cortexuvula/.local/bin/uvx",
     "args": [
       "--from",
       "git+https://github.com/GitGuardian/ggmcp.git",
       "developer-mcp-server"
     ],
     "env": {
       "GITGUARDIAN_URL": "https://dashboard.gitguardian.com",
       "ENABLE_LOCAL_OAUTH": "false",
       "GITGUARDIAN_PERSONAL_ACCESS_TOKEN": "your_token_here"
     }
   }
   ```

3. **Add to `.env`** (safer):
   ```bash
   GITGUARDIAN_PERSONAL_ACCESS_TOKEN=your_token_here
   ```

---

## Using GitGuardian MCP

### Scan Your Project

Ask Claude Code:
```
"Scan this project for exposed secrets using GitGuardian"
```

### Check Specific Files

```
"Check if this file contains any hardcoded secrets"
```

### Manage Incidents

```
"Show me all GitGuardian incidents for this repository"
"Mark this secret as a false positive"
"Help me remediate this exposed API key"
```

### Create Honeytokens

```
"Create a honeytoken for AWS credentials"
```

---

## MCP Server Location

**GitHub Repository**: https://github.com/GitGuardian/ggmcp

**Package**: Installed via `uvx` from Git repository

**Dependencies**: `uv` package manager (already installed at `/home/cortexuvula/.local/bin/uv`)

---

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `GITGUARDIAN_URL` | GitGuardian instance URL | `https://dashboard.gitguardian.com` |
| `ENABLE_LOCAL_OAUTH` | Enable OAuth authentication | `true` |
| `GITGUARDIAN_PERSONAL_ACCESS_TOKEN` | PAT for authentication | Not set |
| `GITGUARDIAN_SCOPES` | API scopes | Auto-configured |

---

## Regional Instances

### EU Instance

If your organization uses the EU instance:

```json
"env": {
  "GITGUARDIAN_URL": "https://dashboard.eu1.gitguardian.com",
  "ENABLE_LOCAL_OAUTH": "true"
}
```

### Self-Hosted Instance

```json
"env": {
  "GITGUARDIAN_URL": "https://dashboard.gitguardian.mycorp.local",
  "ENABLE_LOCAL_OAUTH": "true"
}
```

---

## Custom Scopes (Advanced)

For honeytokens and advanced features:

```json
"env": {
  "GITGUARDIAN_SCOPES": "scan,incidents:read,sources:read,honeytokens:read,honeytokens:write"
}
```

**Available Scopes**:
- `scan` - Scan code for secrets
- `incidents:read` - View security incidents
- `incidents:write` - Manage incidents
- `sources:read` - Access repository sources
- `honeytokens:read` - View honeytokens
- `honeytokens:write` - Create/manage honeytokens

---

## Troubleshooting

### OAuth Not Working

1. Check if browser opens automatically
2. Ensure `ENABLE_LOCAL_OAUTH=true` in `.mcp.json`
3. Check firewall settings
4. Try using PAT instead

### Permission Errors

1. Verify GitGuardian account has necessary permissions
2. Check scopes in configuration
3. Regenerate PAT if using token authentication

### MCP Server Not Loading

1. Verify `uvx` is installed: `which uvx`
2. Check absolute path in `.mcp.json`: `/home/cortexuvula/.local/bin/uvx`
3. Restart Claude Code/IDE
4. Check MCP server logs

---

## Security Best Practices

### ✅ Do's
- ✅ Use OAuth authentication (default)
- ✅ Store PAT in `.env` file (never commit)
- ✅ Review and acknowledge incidents promptly
- ✅ Use honeytokens for monitoring
- ✅ Scan code before committing

### ❌ Don'ts
- ❌ Never commit `.env` file with PAT
- ❌ Don't ignore GitGuardian alerts
- ❌ Don't disable secret scanning
- ❌ Don't hardcode credentials in code

---

## Recent Security Incident

**Context**: This MCP server was added following the resolution of GitGuardian alerts for:
- Neo4j credentials exposed in commit 2596c967
- PostgreSQL URI exposed in commit 2596c967

Both incidents have been **fully remediated** with password rotations. See `SECURITY_INCIDENT_RESOLVED.md` for details.

---

## Additional Resources

- **GitGuardian Blog**: [GitGuardian Launches MCP Server](https://blog.gitguardian.com/gitguardian-launches-its-mcp-server-putting-secrets-security-in-the-developers-hands/)
- **Official Documentation**: https://docs.gitguardian.com/
- **GitHub Repository**: https://github.com/GitGuardian/ggmcp
- **MCP Specification**: https://github.com/modelcontextprotocol

---

## Status

**Installation**: ✅ Complete
**Configuration**: ✅ OAuth enabled
**Authentication**: ⏳ Pending first use (browser OAuth flow)
**Ready to Use**: ✅ Yes

---

**Next Steps**:
1. Restart Claude Code to load the MCP server
2. Ask Claude to scan your project for secrets
3. Review any incidents found
4. Set up automated scanning in your workflow
