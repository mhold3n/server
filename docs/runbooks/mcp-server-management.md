# MCP Server Management Runbook

## Overview
This runbook covers operational procedures for Micro-Capability Platform (MCP) servers on the Birtha platform.

## MCP Architecture

### Core Components
- **MCP Registry**: Central registry for MCP discovery
- **Tool MCPs**: Capability servers (GitHub, Filesystem, etc.)
- **Resource MCPs**: Data servers (Code, Documents, etc.)
- **MCP Client**: Integration layer for AI services

### Service Endpoints
- **MCP Registry**: `http://localhost:8085`
- **GitHub MCP**: `http://localhost:7000`
- **Filesystem MCP**: `http://localhost:7001`
- **Code Resources MCP**: `http://localhost:7002`
- **Document Resources MCP**: `http://localhost:7003`

## Deployment Procedures

### Initial Setup
```bash
# Start MCP registry
docker compose --project-directory "$(pwd)" -f docker-compose.yml -f docker/compose-profiles/docker-compose.ai.yml up -d wrkhrs-mcp

# Start tool MCPs
docker compose --project-directory "$(pwd)" -f docker-compose.yml -f docker/compose-profiles/docker-compose.ai.yml up -d mcp-github mcp-filesystem

# Start resource MCPs
docker compose --project-directory "$(pwd)" -f docker-compose.yml -f docker/compose-profiles/docker-compose.ai.yml up -d mcp-code-resources mcp-doc-resources
```

### MCP Registration
```bash
# Register GitHub MCP
curl -X POST http://localhost:8085/v1/register/tool \
  -H "Content-Type: application/json" \
  -d '{
    "name": "github-mcp",
    "description": "GitHub operations MCP",
    "base_url": "http://mcp-github:7000",
    "api_schema": {"$ref": "http://mcp-github:7000/openapi.json"}
  }'

# Register Filesystem MCP
curl -X POST http://localhost:8085/v1/register/tool \
  -H "Content-Type: application/json" \
  -d '{
    "name": "filesystem-mcp",
    "description": "Filesystem operations MCP",
    "base_url": "http://mcp-filesystem:7001",
    "api_schema": {"$ref": "http://mcp-filesystem:7001/openapi.json"}
  }'
```

## Health Monitoring

### Health Check Endpoints
```bash
# MCP Registry
curl -f http://localhost:8085/health

# GitHub MCP
curl -f http://localhost:7000/health

# Filesystem MCP
curl -f http://localhost:7001/health

# Code Resources MCP
curl -f http://localhost:7002/health

# Document Resources MCP
curl -f http://localhost:7003/health
```

### Service Discovery
```bash
# List all MCPs
curl http://localhost:8085/v1/mcps

# List tool MCPs
curl http://localhost:8085/v1/mcps?mcp_type=tool

# List resource MCPs
curl http://localhost:8085/v1/mcps?mcp_type=resource

# Get specific MCP details
curl http://localhost:8085/v1/mcps/github-mcp
```

### Log Monitoring
```bash
# View MCP registry logs
docker compose --project-directory "$(pwd)" -f docker-compose.yml -f docker/compose-profiles/docker-compose.ai.yml logs wrkhrs-mcp

# View GitHub MCP logs
docker compose --project-directory "$(pwd)" -f docker-compose.yml -f docker/compose-profiles/docker-compose.ai.yml logs mcp-github

# View Filesystem MCP logs
docker compose --project-directory "$(pwd)" -f docker-compose.yml -f docker/compose-profiles/docker-compose.ai.yml logs mcp-filesystem
```

## Troubleshooting

### Common Issues

#### 1. MCP Registry Unavailable
**Symptoms**: 503 errors, MCP discovery failures
**Diagnosis**:
```bash
# Check service status
docker ps | grep wrkhrs-mcp

# Check logs
docker compose --project-directory "$(pwd)" -f docker-compose.yml -f docker/compose-profiles/docker-compose.ai.yml logs wrkhrs-mcp
```
**Resolution**:
- Restart registry: `docker compose --project-directory "$(pwd)" -f docker-compose.yml -f docker/compose-profiles/docker-compose.ai.yml restart wrkhrs-mcp`
- Check database connectivity
- Verify service dependencies

#### 2. MCP Server Connection Issues
**Symptoms**: Connection refused, timeout errors
**Diagnosis**:
```bash
# Check MCP server status
docker ps | grep mcp-

# Test connectivity
curl -f http://localhost:7000/health
```
**Resolution**:
- Restart affected MCP server
- Check network connectivity
- Verify service configuration

#### 3. Tool Discovery Failures
**Symptoms**: Tools not available, MCP not found
**Diagnosis**:
```bash
# Check MCP registration
curl http://localhost:8085/v1/mcps

# Check specific MCP
curl http://localhost:8085/v1/mcps/github-mcp
```
**Resolution**:
- Re-register MCP server
- Check MCP server health
- Verify API schema

#### 4. Resource Access Issues
**Symptoms**: Resource not found, access denied
**Diagnosis**:
```bash
# Check resource MCP status
curl -f http://localhost:7002/health

# Check resource availability
curl http://localhost:7002/v1/resources
```
**Resolution**:
- Restart resource MCP server
- Check data source connectivity
- Verify access permissions

### Performance Issues

#### High Latency
**Symptoms**: Slow MCP responses, timeout errors
**Diagnosis**:
```bash
# Monitor resource usage
docker stats mcp-github

# Check network latency
ping mcp-github
```
**Resolution**:
- Scale MCP servers
- Optimize database queries
- Implement caching

#### Memory Issues
**Symptoms**: Out of memory errors, service crashes
**Diagnosis**:
```bash
# Check memory usage
docker stats mcp-github

# Check logs for OOM errors
docker compose --project-directory "$(pwd)" -f docker-compose.yml -f docker/compose-profiles/docker-compose.ai.yml logs mcp-github
```
**Resolution**:
- Increase memory limits
- Optimize resource usage
- Implement garbage collection

## MCP Server Management

### GitHub MCP Operations
```bash
# Check GitHub MCP status
curl -f http://localhost:7000/health

# Test GitHub operations
curl -X POST http://localhost:7000/v1/tools \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "create_issue",
    "args": {
      "owner": "mhold3n",
      "repo": "server",
      "title": "Test Issue",
      "body": "Test issue body"
    }
  }'
```

### Filesystem MCP Operations
```bash
# Check Filesystem MCP status
curl -f http://localhost:7001/health

# Test filesystem operations
curl -X POST http://localhost:7001/v1/tools \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "read_file",
    "args": {
      "path": "/app/test.txt"
    }
  }'
```

### Code Resources MCP Operations
```bash
# Check Code Resources MCP status
curl -f http://localhost:7002/health

# Test code resource operations
curl -X POST http://localhost:7002/v1/resources \
  -H "Content-Type: application/json" \
  -d '{
    "resource": "search_code",
    "args": {
      "query": "function",
      "limit": 10
    }
  }'
```

### Document Resources MCP Operations
```bash
# Check Document Resources MCP status
curl -f http://localhost:7003/health

# Test document resource operations
curl -X POST http://localhost:7003/v1/resources \
  -H "Content-Type: application/json" \
  -d '{
    "resource": "search_documents",
    "args": {
      "query": "machine learning",
      "limit": 10
    }
  }'
```

## Scaling Procedures

### Horizontal Scaling
```bash
# Scale GitHub MCP
docker compose --project-directory "$(pwd)" -f docker-compose.yml -f docker/compose-profiles/docker-compose.ai.yml up -d --scale mcp-github=3

# Scale Filesystem MCP
docker compose --project-directory "$(pwd)" -f docker-compose.yml -f docker/compose-profiles/docker-compose.ai.yml up -d --scale mcp-filesystem=2
```

### Vertical Scaling
```bash
# Update resource limits in docker/compose-profiles/docker-compose.ai.yml
# Then restart services
docker compose --project-directory "$(pwd)" -f docker-compose.yml -f docker/compose-profiles/docker-compose.ai.yml up -d
```

## Security Management

### Access Control
```bash
# Set up MCP authentication
export MCP_API_KEY="your-api-key"
export MCP_SECRET="your-secret"

# Configure service authentication
# Update MCP server configurations
```

### Data Encryption
```bash
# Enable TLS for MCP servers
# Update MCP server configurations
# Implement certificate management
```

### Audit Logging
```bash
# Enable audit logging
export MCP_AUDIT_LOG=true

# Configure log retention
# Implement log rotation
```

## Backup and Recovery

### Data Backup
```bash
# Backup MCP registry data
docker exec wrkhrs-mcp tar czf /backup/mcp-registry.tar.gz /app/data

# Backup MCP server data
docker exec mcp-github tar czf /backup/github-mcp.tar.gz /app/data
```

### Data Recovery
```bash
# Restore MCP registry data
docker exec wrkhrs-mcp tar xzf /backup/mcp-registry.tar.gz -C /app/data

# Restore MCP server data
docker exec mcp-github tar xzf /backup/github-mcp.tar.gz -C /app/data
```

## Integration Testing

### MCP Connectivity Tests
```bash
# Test MCP registry connectivity
curl -f http://localhost:8085/health

# Test MCP server connectivity
curl -f http://localhost:7000/health
curl -f http://localhost:7001/health
curl -f http://localhost:7002/health
curl -f http://localhost:7003/health
```

### Tool Functionality Tests
```bash
# Test GitHub MCP tools
curl -X POST http://localhost:7000/v1/tools \
  -H "Content-Type: application/json" \
  -d '{"tool": "list_repositories", "args": {"owner": "mhold3n"}}'

# Test Filesystem MCP tools
curl -X POST http://localhost:7001/v1/tools \
  -H "Content-Type: application/json" \
  -d '{"tool": "list_files", "args": {"path": "/app"}}'
```

### Resource Access Tests
```bash
# Test Code Resources MCP
curl -X POST http://localhost:7002/v1/resources \
  -H "Content-Type: application/json" \
  -d '{"resource": "list_code_files", "args": {"limit": 10}}'

# Test Document Resources MCP
curl -X POST http://localhost:7003/v1/resources \
  -H "Content-Type: application/json" \
  -d '{"resource": "list_documents", "args": {"limit": 10}}'
```

## Maintenance Procedures

### Regular Maintenance
```bash
# Weekly health check
make health

# Monthly log cleanup
docker system prune -f

# Quarterly MCP updates
# Update MCP server versions
# Update API schemas
```

### Service Updates
```bash
# Update MCP servers
git pull origin main
docker compose --project-directory "$(pwd)" -f docker-compose.yml -f docker/compose-profiles/docker-compose.ai.yml build
docker compose --project-directory "$(pwd)" -f docker-compose.yml -f docker/compose-profiles/docker-compose.ai.yml up -d

# Verify update
make health
```

## Emergency Procedures

### Service Outage
1. **Immediate Response**:
   - Check service status
   - Review logs
   - Restart affected services

2. **Escalation**:
   - Contact MCP operations team
   - Check infrastructure status
   - Implement fallback procedures

3. **Recovery**:
   - Restore from backup if needed
   - Verify service functionality
   - Update monitoring alerts

### Data Loss
1. **Assessment**:
   - Identify affected data
   - Check backup availability
   - Assess impact

2. **Recovery**:
   - Restore from latest backup
   - Verify data integrity
   - Update service configurations

3. **Prevention**:
   - Review backup procedures
   - Implement additional safeguards
   - Update documentation

## Contact Information

### Support Team
- **Primary**: MCP Operations Team
- **Secondary**: Platform Engineering Team
- **Emergency**: On-call Engineer

### Escalation Path
1. Level 1: MCP Operations Team
2. Level 2: Platform Engineering Team
3. Level 3: Engineering Management
4. Level 4: CTO Office

### Communication Channels
- **Slack**: #mcp-operations
- **Email**: mcp-ops@company.com
- **Phone**: +1-555-MCP-OPS











