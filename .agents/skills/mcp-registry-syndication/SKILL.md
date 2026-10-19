---
name: mcp-registry-syndication
description: >-
  Multi-registry publishing, verification, and syndication guide for MCP servers across the Official
  MCP Registry (registry.modelcontextprotocol.io), Smithery.ai, Glama.ai, and PyPI. Covers server.json
  schema validation, GitHub Device Flow auth, PyPI ownership proof (mcp-name tag), and version lockstep.
---

# MCP Registry Syndication & Distribution Skill

This skill governs the publication, lifecycle maintenance, and cross-directory syndication of Model Context Protocol (MCP) servers across the global ecosystem.

---

## 1. Official MCP Registry (`registry.modelcontextprotocol.io`)

The Official Model Context Protocol Registry is maintained by the MCP steering group and provides standardized discovery for MCP clients (Claude Desktop, Cursor, Zed, Sourcegraph, etc.).

### 1.1 Manifest Specification (`server.json`)
The registry mandates adherence to the official schema: `https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json`.

```json
{
  "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
  "name": "io.github.<Owner>/<repo>",
  "title": "Human-Readable Title",
  "description": "Concise summary under 120 characters.",
  "version": "1.2.2",
  "websiteUrl": "https://github.com/<Owner>/<repo>",
  "packages": [
    {
      "registryType": "pypi",
      "identifier": "<package-name>",
      "version": "1.2.2",
      "transport": {
        "type": "stdio"
      },
      "environmentVariables": [
        {
          "name": "BINANCE_ENV",
          "description": "testnet or mainnet",
          "isRequired": true,
          "isSecret": false
        },
        {
          "name": "BINANCE_READ_API_KEY",
          "description": "Read-only API key",
          "isRequired": true,
          "isSecret": true
        }
      ]
    }
  ]
}
```

### 1.2 Namespace & Ownership Requirements
1. **Reverse-DNS Format**:
   - Format: `io.github.<Owner>/<repo>`
   - Example: `io.github.KumailQazi/krmaazha-binance-mcp`
2. **PyPI Ownership Attestation**:
   - The official registry crawler fetches the published PyPI package README.
   - It requires the HTML comment / subscript tag:
     ```markdown
     <sub>mcp-name: io.github.<Owner>/<repo></sub>
     ```
   - If this marker is missing from the package on PyPI, the publishing command will fail with an authorization/ownership mismatch error.

### 1.3 Publishing Workflow via `mcp-publisher`
1. **Authentication (GitHub Device Flow)**:
   ```bash
   npx -y mcp-publisher login github
   ```
   Follow the one-time device code prompt at `https://github.com/login/device`.
2. **Validation & Dry Run**:
   ```bash
   npx -y mcp-publisher publish --dry-run
   ```
3. **Live Publishing**:
   ```bash
   npx -y mcp-publisher publish
   ```
4. **Verification**:
   Inspect active registry entry:
   `https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.<Owner>/<repo>`

---

## 2. Directory Syndication Formats

### 2.1 Smithery.ai (`smithery.yaml`)
Smithery enables one-click CLI and web deployment (`npx -y @smithery/cli run ...`).
Create `smithery.yaml` in repository root:
```yaml
startCommand:
  type: stdio
  configSchema:
    type: object
    properties:
      BINANCE_ENV:
        type: string
        default: "testnet"
        description: "Binance environment (testnet or mainnet)"
      BINANCE_READ_API_KEY:
        type: string
        description: "Read-only Binance API key"
      BINANCE_READ_API_SECRET:
        type: string
        description: "Read-only Binance API secret"
    required:
      - BINANCE_ENV
      - BINANCE_READ_API_KEY
      - BINANCE_READ_API_SECRET
  commandFunction:
    bash: "uvx krmaazha-binance-mcp"
    powershell: "uvx krmaazha-binance-mcp"
```

### 2.2 Glama.ai (`glama.json`)
Glama provides online inspection, schema visualization, and directory ranking.
Create `glama.json` in repository root:
```json
{
  "$schema": "https://glama.ai/mcp/schemas/server.json",
  "name": "krmaazha-binance-mcp",
  "description": "Security-first Binance MCP with physical confirmation gate and quant research.",
  "transport": "stdio",
  "command": "uvx",
  "args": ["krmaazha-binance-mcp"]
}
```

---

## 3. Version Lockstep Anti-Drift Checklist

Before any release:
1. `pyproject.toml` version matches target release (e.g. `1.2.2`).
2. `server.json` version matches `pyproject.toml`.
3. `server.json` package version matches `pyproject.toml`.
4. `CHANGELOG.md` contains top versioned section `## [1.2.2] — YYYY-MM-DD`.
5. Run consistency gate:
   ```bash
   pytest tests/test_consistency.py
   ```
