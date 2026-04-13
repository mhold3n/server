# Example Per-Repo MCP Server

This is an example of a **per-repo MCP server** that provides project-specific tools and capabilities. Unlike global MCP servers that run on the control plane, this server is designed to be deployed alongside or within individual project repositories.

## Architecture

This MCP server implements the **hybrid MCP architecture** where:
- **Global MCP servers** (GitHub, filesystem, secrets, vector-db) run on the control plane
- **Per-repo MCP servers** like this one provide project-specific capabilities

## Features

### Code Indexing
- **Tree-sitter parsing** for Python, JavaScript, TypeScript
- **AST analysis** for functions, classes, imports
- **Fast search** across indexed codebase
- **Language detection** and file type filtering

### Dependency Analysis
- **Multi-language support** (Python, Node.js, Rust, Go)
- **Dependency graph** construction
- **Vulnerability checking** (placeholder for real vulnerability databases)
- **Outdated dependency detection**

### Project Analysis
- **Project type detection** (Python, Node.js, Rust, Go, Java, etc.)
- **Code metrics** (lines of code, file counts, language distribution)
- **Structure analysis** (directories, key files, depth)
- **Documentation analysis** (README, CHANGELOG, etc.)
- **Testing setup analysis** (test files, frameworks)
- **CI/CD configuration analysis**

## API Endpoints

### Health Check
```http
GET /health
```

### Index Codebase
```http
POST /index
Content-Type: application/json

{
  "path": "/path/to/codebase",
  "languages": ["python", "javascript", "typescript"],
  "include_tests": true
}
```

### Search Codebase
```http
POST /search
Content-Type: application/json

{
  "query": "function_name",
  "file_types": ["python"],
  "max_results": 10
}
```

### Analyze Dependencies
```http
POST /analyze-dependencies
Content-Type: application/json

{
  "path": "/path/to/project"
}
```

### Get Project Info
```http
POST /project-info
Content-Type: application/json

{
  "path": "/path/to/project"
}
```

### Get Statistics
```http
GET /stats
```

## Installation

### Prerequisites
- Python 3.11+
- Poetry or pip
- Tree-sitter language parsers

### Setup
```bash
# Install dependencies
poetry install

# Or with pip
pip install -e .

# Run the server
poetry run mcp-server

# Or directly
python -m src.mcp_server
```

## Configuration

### Environment Variables
```bash
# Server configuration
MCP_SERVER_HOST=0.0.0.0
MCP_SERVER_PORT=7004

# Logging
LOG_LEVEL=INFO

# Tree-sitter parsers
TREE_SITTER_PYTHON_PATH=/path/to/tree-sitter-python
TREE_SITTER_JAVASCRIPT_PATH=/path/to/tree-sitter-javascript
TREE_SITTER_TYPESCRIPT_PATH=/path/to/tree-sitter-typescript
```

### Docker
```bash
# Build image
docker build -t example-repo-mcp .

# Run container
docker run -p 7004:7004 example-repo-mcp
```

## Integration with Agent Orchestrator

### Router Configuration
Add to `services/router/config/mcp_servers.yaml`:

```yaml
mcp_servers:
  - name: "example-repo-mcp"
    url: "http://example-repo-mcp:7004"
    type: "per-repo"
    capabilities:
      - "code_indexing"
      - "dependency_analysis"
      - "project_analysis"
    health_endpoint: "/health"
    timeout: 30
```

### Docker Compose
Add to your project's `docker-compose.yml`:

```yaml
services:
  example-repo-mcp:
    build: ./mcp/servers/example-repo-mcp
    ports:
      - "7004:7004"
    volumes:
      - .:/workspace
    working_dir: /workspace
    environment:
      - MCP_SERVER_HOST=0.0.0.0
      - MCP_SERVER_PORT=7004
    restart: unless-stopped
```

## Usage Examples

### Index a Python Project
```python
import httpx

async def index_project():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:7004/index",
            json={
                "path": "/path/to/python/project",
                "languages": ["python"],
                "include_tests": True
            }
        )
        return response.json()

# Index the project
result = await index_project()
print(f"Indexed {result['indexed_files']} files")
```

### Search for Functions
```python
async def search_functions():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:7004/search",
            json={
                "query": "def test_",
                "file_types": ["python"],
                "max_results": 5
            }
        )
        return response.json()

# Search for test functions
results = await search_functions()
for result in results["results"]:
    print(f"Found in {result['file']}: {result['matches']}")
```

### Analyze Dependencies
```python
async def analyze_deps():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:7004/analyze-dependencies",
            json={"path": "/path/to/project"}
        )
        return response.json()

# Analyze project dependencies
analysis = await analyze_deps()
print(f"Project type: {analysis['project_type']}")
print(f"Dependencies: {analysis['dependencies']}")
```

## Customization

### Adding New Languages
1. Install tree-sitter parser for the language
2. Add language configuration in `code_indexer.py`
3. Update file extension mappings
4. Add language-specific analysis logic

### Adding New Analysis Features
1. Create new analyzer class in `src/`
2. Add endpoint in `mcp_server.py`
3. Update tests in `tests/`
4. Document new capabilities

### Extending Dependency Analysis
1. Add support for new package managers
2. Integrate with real vulnerability databases
3. Add dependency update recommendations
4. Implement dependency conflict detection

## Testing

```bash
# Run tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=src --cov-report=html

# Run specific test
poetry run pytest tests/test_mcp_server.py::TestIndexCodebase::test_index_codebase_success
```

## Development

### Code Quality
```bash
# Lint code
poetry run ruff check src tests

# Format code
poetry run black src tests

# Type check
poetry run mypy src
```

### Adding New Features
1. Create feature branch
2. Implement feature with tests
3. Update documentation
4. Submit pull request

## Deployment

### Local Development
```bash
# Start server
poetry run mcp-server

# Test endpoints
curl http://localhost:7004/health
```

### Production
```bash
# Build Docker image
docker build -t example-repo-mcp:latest .

# Deploy with docker-compose
docker-compose up -d example-repo-mcp
```

## Troubleshooting

### Common Issues

#### Tree-sitter Parser Errors
```bash
# Reinstall tree-sitter parsers
pip uninstall tree-sitter-python tree-sitter-javascript tree-sitter-typescript
pip install tree-sitter-python tree-sitter-javascript tree-sitter-typescript
```

#### Memory Issues with Large Codebases
```bash
# Increase memory limits
export MCP_SERVER_MAX_MEMORY=2G
```

#### Slow Indexing
```bash
# Exclude large directories
export MCP_SERVER_EXCLUDE_DIRS="node_modules,__pycache__,.git"
```

### Logs
```bash
# View server logs
docker logs example-repo-mcp

# Enable debug logging
export LOG_LEVEL=DEBUG
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details.
