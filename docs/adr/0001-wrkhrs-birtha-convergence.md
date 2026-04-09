# ADR-0001: WrkHrs + Birtha Convergence Strategy

## Status
Accepted

## Context
We need to integrate the WrkHrs AI services stack with the existing Birtha platform orchestration system. WrkHrs provides a complete AI microservices architecture with domain-specific tools, while Birtha provides platform orchestration, MCP servers, and infrastructure services.

## Decision
We will merge WrkHrs into Birtha as the canonical AI backend, extending existing Birtha services with WrkHrs patterns rather than replacing them.

### Key Decisions:

1. **Vendor WrkHrs**: Clone WrkHrs repository into `services/wrkhrs/` as the canonical AI implementation
2. **Extend Existing Services**: Enhance Birtha's API and Router services with WrkHrs capabilities
3. **CPU/GPU Split**: Run orchestrator on CPU (Birtha server), LLM runner on GPU (workstation)
4. **Unified Configuration**: Merge environment configurations into existing Birtha templates
5. **Docker Compose Integration**: Add new compose files for AI stack and platform services

## Rationale

### Why Vendor WrkHrs?
- Preserves the complete WrkHrs AI stack as a cohesive unit
- Maintains version tracking with `.wrkhrs-version` file
- Allows for future upstream updates while maintaining customizations
- Provides clear separation between platform (Birtha) and AI (WrkHrs) concerns

### Why Extend Rather Than Replace?
- Preserves existing Birtha functionality and integrations
- Maintains backward compatibility with current deployments
- Allows gradual migration and testing of new AI capabilities
- Leverages existing MCP server infrastructure

### Why CPU/GPU Split?
- Optimizes resource utilization (CPU for orchestration, GPU for inference)
- Enables scaling of LLM inference independently from orchestration
- Supports multiple GPU workstations for distributed inference
- Maintains clear separation of concerns

## Implementation

### Phase 1: Foundation
- Clone WrkHrs into `services/wrkhrs/`
- Merge environment configurations
- Create `compose/docker-compose.ai.yml` for WrkHrs services
- Create `compose/docker-compose.platform.yml` for MLflow/observability

### Phase 2: Service Integration
- Extend `services/api` with WrkHrs gateway client
- Extend `services/router` with orchestrator client and LangChain/LangGraph
- Create unified MCP registry service
- Add observability with MLflow logging

### Phase 3: Policy & Quality
- Implement policy middleware for answer quality
- Add evidence and citation requirements
- Create evaluation harness with golden test sets
- Implement human-in-the-loop feedback

## Consequences

### Positive
- Unified platform with comprehensive AI capabilities
- Maintains existing Birtha functionality
- Clear separation of concerns (platform vs AI)
- Scalable architecture with CPU/GPU split
- Full observability and experiment tracking

### Negative
- Increased complexity with multiple compose files
- Larger codebase with vendored WrkHrs
- More services to monitor and maintain
- Potential for configuration drift between environments

### Risks
- Integration complexity between Birtha and WrkHrs services
- Performance overhead from service communication
- Configuration management across multiple environments
- Version synchronization between Birtha and WrkHrs

## Mitigation Strategies
- Comprehensive health checks and monitoring
- Clear documentation and runbooks
- Automated testing and validation
- Gradual rollout with feature flags
- Regular dependency updates and security patches

## Related ADRs
- ADR-0002: MCP Hybrid Architecture (Tool vs Resource MCPs)
- ADR-0003: CPU-GPU Split Architecture
- ADR-0004: MLflow Provenance Tracking
- ADR-0005: Policy Middleware for Answer Quality











