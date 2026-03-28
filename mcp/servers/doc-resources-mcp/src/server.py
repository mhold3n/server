"""MCP server for PDF/textbook datasets with chunking and content hashing."""

import os
import json
from typing import Any, Dict, List, Optional

import structlog
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from .ingest import DocumentIngester
from .chunking import DocumentChunker

logger = structlog.get_logger()

app = FastAPI(
    title="Document Resources MCP Server",
    description="MCP server for PDF/textbook datasets with chunking and content hashing",
    version="0.1.0",
)

# Initialize components
qdrant_client = QdrantClient(
    host=os.getenv("QDRANT_HOST", "localhost"),
    port=int(os.getenv("QDRANT_PORT", "6333")),
)

embedder = SentenceTransformer(
    model_name_or_path=os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
)

chunker = DocumentChunker(
    chunk_size=int(os.getenv("CHUNK_SIZE", "500")),
    chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "50")),
)

ingester = DocumentIngester(
    qdrant_client=qdrant_client,
    embedder=embedder,
    chunker=chunker,
)


class DocumentResource(BaseModel):
    """Document resource model."""
    
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
    
    results: List[DocumentResource]
    total: int
    query: str


@app.on_event("startup")
async def startup_event():
    """Initialize the server."""
    try:
        # Initialize Qdrant collection
        await ingester.initialize_collection()
        logger.info("Document resources MCP server started successfully")
    except Exception as e:
        logger.error("Failed to start document resources MCP server", error=str(e))
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check Qdrant connection
        collections = qdrant_client.get_collections()
        
        return {
            "status": "healthy",
            "service": "doc-resources-mcp",
            "qdrant_collections": len(collections.collections),
        }
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "service": "doc-resources-mcp",
            "error": str(e),
        }


@app.post("/v1/search", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
) -> SearchResponse:
    """Search document resources.
    
    Args:
        request: Search request
        
    Returns:
        Search results
        
    Raises:
        HTTPException: If search fails
    """
    try:
        # Generate query embedding
        query_embedding = embedder.encode(request.query).tolist()
        
        # Search in Qdrant
        search_results = qdrant_client.search(
            collection_name="document_resources",
            query_vector=query_embedding,
            limit=request.limit,
            query_filter=request.filters,
        )
        
        # Convert results to DocumentResource objects
        results = []
        for result in search_results:
            resource = DocumentResource(
                id=result.id,
                content=result.payload["content"],
                metadata=result.payload["metadata"],
                embeddings=result.vector,
                provenance=result.payload["provenance"],
            )
            results.append(resource)
        
        logger.info(
            "Document search completed",
            query=request.query,
            results_count=len(results),
        )
        
        return SearchResponse(
            results=results,
            total=len(results),
            query=request.query,
        )
        
    except Exception as e:
        logger.error("Document search failed", query=request.query, error=str(e))
        raise HTTPException(status_code=500, detail="Search failed")


@app.get("/v1/resources/{resource_id}")
async def get_resource(resource_id: str) -> DocumentResource:
    """Get a specific document resource.
    
    Args:
        resource_id: Resource ID
        
    Returns:
        Document resource
        
    Raises:
        HTTPException: If resource not found
    """
    try:
        # Get resource from Qdrant
        result = qdrant_client.retrieve(
            collection_name="document_resources",
            ids=[resource_id],
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        resource_data = result[0]
        
        resource = DocumentResource(
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


@app.post("/v1/ingest")
async def ingest_document(
    file: UploadFile = File(...),
    metadata: Optional[str] = None,
) -> Dict[str, Any]:
    """Ingest a document.
    
    Args:
        file: Document file to ingest
        metadata: Optional metadata JSON string
        
    Returns:
        Ingestion results
        
    Raises:
        HTTPException: If ingestion fails
    """
    try:
        # Parse metadata
        doc_metadata = {}
        if metadata:
            doc_metadata = json.loads(metadata)
        
        # Read file content
        content = await file.read()
        
        # Ingest document
        results = await ingester.ingest_document(
            filename=file.filename,
            content=content,
            metadata=doc_metadata,
        )
        
        logger.info(
            "Document ingested successfully",
            filename=file.filename,
            chunks_created=results["chunks_created"],
        )
        
        return results
        
    except Exception as e:
        logger.error("Document ingestion failed", filename=file.filename, error=str(e))
        raise HTTPException(status_code=500, detail="Ingestion failed")


@app.post("/v1/ingest/batch")
async def ingest_documents_batch(
    files: List[UploadFile] = File(...),
    metadata: Optional[str] = None,
) -> Dict[str, Any]:
    """Ingest multiple documents.
    
    Args:
        files: List of document files to ingest
        metadata: Optional metadata JSON string
        
    Returns:
        Batch ingestion results
        
    Raises:
        HTTPException: If ingestion fails
    """
    try:
        # Parse metadata
        doc_metadata = {}
        if metadata:
            doc_metadata = json.loads(metadata)
        
        # Ingest documents
        results = await ingester.ingest_documents_batch(
            files=files,
            metadata=doc_metadata,
        )
        
        logger.info(
            "Batch document ingestion completed",
            files_processed=results["files_processed"],
            chunks_created=results["chunks_created"],
        )
        
        return results
        
    except Exception as e:
        logger.error("Batch document ingestion failed", error=str(e))
        raise HTTPException(status_code=500, detail="Batch ingestion failed")


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
        JSON schema for document resources
    """
    return {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "Unique resource identifier"},
            "content": {"type": "string", "description": "Document content"},
            "metadata": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Original filename"},
                    "file_type": {"type": "string", "description": "File type (pdf, docx, txt, etc.)"},
                    "page_number": {"type": "integer", "description": "Page number"},
                    "chunk_index": {"type": "integer", "description": "Chunk index within document"},
                    "chunk_size": {"type": "integer", "description": "Chunk size in characters"},
                    "title": {"type": "string", "description": "Document title"},
                    "author": {"type": "string", "description": "Document author"},
                    "subject": {"type": "string", "description": "Document subject"},
                    "keywords": {"type": "array", "items": {"type": "string"}, "description": "Document keywords"},
                },
            },
            "provenance": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "Source of the document"},
                    "ingested_at": {"type": "string", "description": "Ingestion timestamp"},
                    "content_hash": {"type": "string", "description": "Content hash for integrity"},
                    "file_size": {"type": "integer", "description": "Original file size"},
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
        port=7003,
        reload=True,
    )











