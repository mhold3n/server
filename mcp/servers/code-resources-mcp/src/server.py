"""MCP server for indexed codebase datasets with embeddings and provenance."""

import os
from typing import Any, Dict, List, Optional

import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from qdrant_client import QdrantClient

from .indexer import CodeIndexer
from .embeddings import CodeEmbedder

logger = structlog.get_logger()

app = FastAPI(
    title="Code Resources MCP Server",
    description="MCP server for indexed codebase datasets with embeddings and provenance",
    version="0.1.0",
)

# Initialize components
qdrant_client = QdrantClient(
    host=os.getenv("QDRANT_HOST", "localhost"),
    port=int(os.getenv("QDRANT_PORT", "6333")),
)

embedder = CodeEmbedder(
    model_name=os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
)

indexer = CodeIndexer(
    qdrant_client=qdrant_client,
    embedder=embedder,
)


class CodeResource(BaseModel):
    """Code resource model."""
    
    id: str
    content: str
    metadata: Dict[str, Any]
    embeddings: Optional[List[float]] = None
    provenance: Dict[str, Any]


class SearchRequest(BaseModel):
    """Search request model."""
    
    query: str
    limit: int = 10
    filters: Optional[Dict[str, Any]] = None


class SearchResponse(BaseModel):
    """Search response model."""
    
    results: List[CodeResource]
    total: int
    query: str


@app.on_event("startup")
async def startup_event():
    """Initialize the server."""
    try:
        # Initialize Qdrant collection
        await indexer.initialize_collection()
        logger.info("Code resources MCP server started successfully")
    except Exception as e:
        logger.error("Failed to start code resources MCP server", error=str(e))
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check Qdrant connection
        collections = qdrant_client.get_collections()
        
        return {
            "status": "healthy",
            "service": "code-resources-mcp",
            "qdrant_collections": len(collections.collections),
        }
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "service": "code-resources-mcp",
            "error": str(e),
        }


@app.post("/v1/search", response_model=SearchResponse)
async def search_code(
    request: SearchRequest,
) -> SearchResponse:
    """Search code resources.
    
    Args:
        request: Search request
        
    Returns:
        Search results
        
    Raises:
        HTTPException: If search fails
    """
    try:
        # Generate query embedding
        query_embedding = embedder.embed_text(request.query)
        
        # Search in Qdrant
        search_results = qdrant_client.search(
            collection_name="code_resources",
            query_vector=query_embedding,
            limit=request.limit,
            query_filter=request.filters,
        )
        
        # Convert results to CodeResource objects
        results = []
        for result in search_results:
            resource = CodeResource(
                id=result.id,
                content=result.payload["content"],
                metadata=result.payload["metadata"],
                embeddings=result.vector,
                provenance=result.payload["provenance"],
            )
            results.append(resource)
        
        logger.info(
            "Code search completed",
            query=request.query,
            results_count=len(results),
        )
        
        return SearchResponse(
            results=results,
            total=len(results),
            query=request.query,
        )
        
    except Exception as e:
        logger.error("Code search failed", query=request.query, error=str(e))
        raise HTTPException(status_code=500, detail="Search failed")


@app.get("/v1/resources/{resource_id}")
async def get_resource(resource_id: str) -> CodeResource:
    """Get a specific code resource.
    
    Args:
        resource_id: Resource ID
        
    Returns:
        Code resource
        
    Raises:
        HTTPException: If resource not found
    """
    try:
        # Get resource from Qdrant
        result = qdrant_client.retrieve(
            collection_name="code_resources",
            ids=[resource_id],
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        resource_data = result[0]
        
        resource = CodeResource(
            id=resource_data.id,
            content=resource_data.payload["content"],
            metadata=resource_data.payload["metadata"],
            embeddings=resource_data.vector,
            provenance=resource_data.payload["provenance"],
        )
        
        return resource
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get resource", resource_id=resource_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get resource")


@app.post("/v1/index")
async def index_repository(
    repository_path: str,
    branch: str = "main",
) -> Dict[str, Any]:
    """Index a code repository.
    
    Args:
        repository_path: Path to repository
        branch: Branch to index
        
    Returns:
        Indexing results
        
    Raises:
        HTTPException: If indexing fails
    """
    try:
        # Index the repository
        results = await indexer.index_repository(
            repository_path=repository_path,
            branch=branch,
        )
        
        logger.info(
            "Repository indexed successfully",
            repository_path=repository_path,
            branch=branch,
            files_indexed=results["files_indexed"],
            functions_indexed=results["functions_indexed"],
        )
        
        return results
        
    except Exception as e:
        logger.error(
            "Repository indexing failed",
            repository_path=repository_path,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail="Indexing failed")


@app.get("/v1/collections")
async def list_collections() -> Dict[str, Any]:
    """List available collections.
    
    Returns:
        List of collections
    """
    try:
        collections = qdrant_client.get_collections()
        
        return {
            "collections": [
                {
                    "name": collection.name,
                    "vectors_count": collection.vectors_count,
                    "indexed_vectors_count": collection.indexed_vectors_count,
                }
                for collection in collections.collections
            ],
        }
        
    except Exception as e:
        logger.error("Failed to list collections", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list collections")


@app.get("/v1/schema")
async def get_schema() -> Dict[str, Any]:
    """Get resource schema.
    
    Returns:
        JSON schema for code resources
    """
    return {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "Unique resource identifier"},
            "content": {"type": "string", "description": "Code content"},
            "metadata": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "File path"},
                    "function_name": {"type": "string", "description": "Function name"},
                    "class_name": {"type": "string", "description": "Class name"},
                    "language": {"type": "string", "description": "Programming language"},
                    "line_start": {"type": "integer", "description": "Start line number"},
                    "line_end": {"type": "integer", "description": "End line number"},
                },
            },
            "provenance": {
                "type": "object",
                "properties": {
                    "repository": {"type": "string", "description": "Repository URL"},
                    "commit_sha": {"type": "string", "description": "Commit SHA"},
                    "branch": {"type": "string", "description": "Branch name"},
                    "indexed_at": {"type": "string", "description": "Indexing timestamp"},
                },
            },
        },
        "required": ["id", "content", "metadata", "provenance"],
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=7002,
        reload=True,
    )











