# MCP Servers Architecture

This directory contains the Model Context Protocol (MCP) servers for the agent-orchestrator system. The architecture follows a hybrid approach with both global infrastructure-level servers and per-repository servers.

## Hybrid Architecture Overview

| Dimension                    | Install **globally** on control plane                                                    | Install **per-repo** (in the project)                                        |
| ---------------------------- | ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| **Scope & reuse**            | Cross-project tools (GitHub, Jira, search, vector DB, secrets broker, artifact registry) | Repo-unique tools (custom code indexer, domain schema, one-off integrations) |
| **Versioning stability**     | You want **one version** for all teams; change managed by infra                          | The repo must **pin** exact versions compatible with its code/tooling        |
| **Security & secrets**       | Centralized secret custody, auditing, network ACLs                                       | Least-privilege, repo-scoped tokens, sandboxes per project                   |
| **Isolation / blast radius** | Lower isolation (shared process) unless namespaced                                       | High isolation; failures/updates affect only that repo                       |
| **Reproducibility / CI**     | Good for common infra; less deterministic per-repo without careful tagging               | Strong: repo contains its MCP stack → portable dev/CI                        |
| **Performance / caching**    | Shared caches (code search, embeddings) benefit all repos                                | Tailored indexes/caches per repo; no cross-pollution                         |
| **Ops overhead**             | Lower (one place to patch/observe)                                                       | Higher (N stacks), but automated with templates                              |

## Global MCP Servers (Control Plane)

These servers run on the control plane and provide shared infrastructure capabilities:

### 1. GitHub MCP Server (`github-mcp/`)
- **Purpose**: Repository operations, issue tracking, pull request management
- **Port**: 7000
- **Tools**: 
  - `search_repositories`: Search for repositories
  - `get_repository`: Get repository information
  - `list_issues`: List repository issues
  - `create_issue`: Create new issues
  - `list_pull_requests`: List pull requests
  - `get_file_contents`: Get file contents from repository
- **Configuration**: Requires `GITHUB_TOKEN` environment variable

### 2. Filesystem MCP Server (`filesystem-mcp/`)
- **Purpose**: File operations, code analysis, dependency tracking
- **Port**: 7001
- **Tools**:
  - `read_file`: Read file contents
  - `write_file`: Write file contents
  - `list_directory`: List directory contents
  - `search_files`: Search for files by pattern
  - `search_content`: Search for content within files
  - `analyze_code`: Analyze code structure and dependencies
  - `get_dependencies`: Get project dependencies
- **Security**: Restricted to `/workspace` directory

### 3. Secrets MCP Server (`secrets-mcp/`)
- **Purpose**: Secure secrets management and retrieval
- **Port**: 7002
- **Tools**:
  - `get_secret`: Retrieve secrets via Connect (`op://...` refs)
  - `set_secret`: Store secrets via Connect
  - `list_secrets`: List available secrets
  - `delete_secret`: Delete secrets
  - `encrypt_data`: Encrypt data locally
  - `decrypt_data`: Decrypt data locally
- **Backend**: 1Password Connect backend (resolves `op://<vault>/<item>/<field>` references)

### 4. Vector DB MCP Server (`vector-db-mcp/`)
- **Purpose**: Vector database operations for embeddings and search
- **Port**: 7003
- **Tools**:
  - `create_collection`: Create vector collections
  - `list_collections`: List all collections
  - `upsert_vectors`: Insert/update vectors
  - `search_vectors`: Search for similar vectors
  - `search_by_text`: Search using text queries
  - `delete_vectors`: Delete vectors
  - `get_collection_info`: Get collection information
- **Backend**: Qdrant vector database

## Per-Repository MCP Servers

These servers are designed to be integrated into individual project repositories:

### Example: Custom Code Indexer (`example-repo-mcp/`)
- **Purpose**: Project-specific code analysis and indexing
- **Integration**: Copy to your project repository
- **Customization**: Modify for your specific domain and requirements

## Configuration

### Global Server Configuration
Global MCP servers are configured in `config/mcp_servers.yaml`:

```yaml
servers:
  - name: github-mcp
    type: http
    url: http://mcp-github:7000
    description: "GitHub integration for repository operations"
    capabilities:
      - repository_management
      - issue_tracking
      - pull_request_operations
      - code_search
```

### Environment Variables
Each server requires specific environment variables:

```bash
# GitHub MCP
GITHUB_TOKEN=ghp_your_token_here
GITHUB_OWNER=your-org
GITHUB_REPO=your-repo

# Secrets MCP
OP_CONNECT_HOST=http://connect-api:8080
OP_CONNECT_TOKEN=your-connect-token
ENCRYPTION_KEY=your-32-char-encryption-key

# Vector DB MCP
QDRANT_URL=http://qdrant:6333
```

## Development

### Adding New Global MCP Servers
1. Create a new directory under `mcp/servers/`
2. Implement the MCP server following the existing patterns
3. Add to `docker-compose.server.yml`
4. Update `config/mcp_servers.yaml`
5. Add tests and documentation

### Creating Per-Repository MCP Servers
1. Use `example-repo-mcp/` as a template
2. Customize for your specific needs
3. Integrate into your project's CI/CD pipeline
4. Document the integration process

## Security Considerations

### Global Servers
- Run with minimal required permissions
- Use network isolation (Docker networks)
- Implement proper authentication and authorization
- Regular security updates and monitoring

### Per-Repository Servers
- Sandbox execution environments
- Project-scoped access tokens
- Regular dependency updates
- Security scanning in CI/CD

## Monitoring and Observability

All MCP servers expose health check endpoints and metrics:
- Health: `GET /health`
- Metrics: `GET /metrics` (Prometheus format)
- Tools: `GET /tools`

## Troubleshooting

### Common Issues
1. **Connection failures**: Check network connectivity and firewall rules
2. **Authentication errors**: Verify environment variables and tokens
3. **Permission denied**: Check file system permissions and access controls
4. **Resource limits**: Monitor memory and CPU usage

### Debugging
- Enable debug logging by setting `LOG_LEVEL=DEBUG`
- Check container logs: `docker logs <container-name>`
- Verify service health: `curl http://<service>:<port>/health`

## Contributing

1. Follow the existing code patterns and structure
2. Add comprehensive tests for new functionality
3. Update documentation for any changes
4. Ensure security best practices are followed
5. Test with both global and per-repository scenarios
