"""Vector database operations MCP server."""

import json
import os
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from qdrant_client.http import models

from .embedding_service import EmbeddingService

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

app = FastAPI(title="Vector DB MCP Server", version="0.1.0")

# Global services
embedding_service = EmbeddingService()
qdrant_client = None


class ToolRequest(BaseModel):
    """Tool request model."""

    tool: str = Field(..., description="Tool name")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Tool arguments")


class ToolResponse(BaseModel):
    """Tool response model."""

    content: list[dict[str, str]] = Field(..., description="Response content")


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global qdrant_client

    try:
        qdrant_url = os.getenv("QDRANT_URL", "http://qdrant:6333")
        qdrant_client = QdrantClient(url=qdrant_url)

        # Test connection
        collections = qdrant_client.get_collections()
        logger.info("Connected to Qdrant", url=qdrant_url, collections=len(collections.collections))

    except Exception as e:
        logger.error("Failed to connect to Qdrant", error=str(e))
        qdrant_client = None


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        qdrant_healthy = qdrant_client is not None
        if qdrant_healthy:
            try:
                qdrant_client.get_collections()
            except Exception:
                qdrant_healthy = False

        return {
            "status": "healthy" if qdrant_healthy else "degraded",
            "service": "vector-db-mcp",
            "qdrant_connected": qdrant_healthy,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "vector-db-mcp",
            "error": str(e),
        }


@app.get("/tools")
async def list_tools():
    """List available tools."""
    return {
        "tools": [
            {
                "name": "create_collection",
                "description": "Create a new vector collection",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Collection name"},
                        "vector_size": {"type": "integer", "description": "Vector dimension size"},
                        "distance": {"type": "string", "enum": ["Cosine", "Euclid", "Dot"], "description": "Distance metric"},
                    },
                    "required": ["name", "vector_size"],
                },
            },
            {
                "name": "list_collections",
                "description": "List all collections",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "upsert_vectors",
                "description": "Insert or update vectors in a collection",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "collection": {"type": "string", "description": "Collection name"},
                        "points": {"type": "array", "description": "List of points to upsert"},
                    },
                    "required": ["collection", "points"],
                },
            },
            {
                "name": "search_vectors",
                "description": "Search for similar vectors",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "collection": {"type": "string", "description": "Collection name"},
                        "query_vector": {"type": "array", "description": "Query vector"},
                        "limit": {"type": "integer", "description": "Number of results to return"},
                        "score_threshold": {"type": "number", "description": "Minimum similarity score"},
                    },
                    "required": ["collection", "query_vector"],
                },
            },
            {
                "name": "search_by_text",
                "description": "Search for similar vectors using text query",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "collection": {"type": "string", "description": "Collection name"},
                        "query_text": {"type": "string", "description": "Text query"},
                        "limit": {"type": "integer", "description": "Number of results to return"},
                        "score_threshold": {"type": "number", "description": "Minimum similarity score"},
                    },
                    "required": ["collection", "query_text"],
                },
            },
            {
                "name": "delete_vectors",
                "description": "Delete vectors from a collection",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "collection": {"type": "string", "description": "Collection name"},
                        "ids": {"type": "array", "description": "Vector IDs to delete"},
                    },
                    "required": ["collection", "ids"],
                },
            },
            {
                "name": "get_collection_info",
                "description": "Get information about a collection",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "collection": {"type": "string", "description": "Collection name"},
                    },
                    "required": ["collection"],
                },
            },
        ]
    }


@app.post("/call", response_model=ToolResponse)
async def call_tool(request: ToolRequest):
    """Call a tool with the given arguments."""
    if not qdrant_client:
        raise HTTPException(status_code=503, detail="Qdrant client not connected")

    try:
        logger.info(
            "Calling tool",
            tool=request.tool,
            arguments=request.arguments,
        )

        if request.tool == "create_collection":
            result = await create_collection(
                request.arguments["name"],
                request.arguments["vector_size"],
                request.arguments.get("distance", "Cosine"),
            )
        elif request.tool == "list_collections":
            result = await list_collections()
        elif request.tool == "upsert_vectors":
            result = await upsert_vectors(
                request.arguments["collection"],
                request.arguments["points"],
            )
        elif request.tool == "search_vectors":
            result = await search_vectors(
                request.arguments["collection"],
                request.arguments["query_vector"],
                request.arguments.get("limit", 10),
                request.arguments.get("score_threshold"),
            )
        elif request.tool == "search_by_text":
            result = await search_by_text(
                request.arguments["collection"],
                request.arguments["query_text"],
                request.arguments.get("limit", 10),
                request.arguments.get("score_threshold"),
            )
        elif request.tool == "delete_vectors":
            result = await delete_vectors(
                request.arguments["collection"],
                request.arguments["ids"],
            )
        elif request.tool == "get_collection_info":
            result = await get_collection_info(request.arguments["collection"])
        else:
            raise HTTPException(status_code=400, detail=f"Unknown tool: {request.tool}")

        return ToolResponse(content=[{"type": "text", "text": result}])

    except Exception as e:
        logger.error(
            "Tool call failed",
            tool=request.tool,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


async def create_collection(name: str, vector_size: int, distance: str = "Cosine") -> str:
    """Create a new collection."""
    try:
        # Map distance string to Qdrant distance
        distance_map = {
            "Cosine": models.Distance.COSINE,
            "Euclid": models.Distance.EUCLID,
            "Dot": models.Distance.DOT,
        }

        qdrant_distance = distance_map.get(distance, models.Distance.COSINE)

        # Create collection
        qdrant_client.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=qdrant_distance,
            ),
        )

        logger.info("Collection created", name=name, vector_size=vector_size, distance=distance)

        return json.dumps({
            "name": name,
            "vector_size": vector_size,
            "distance": distance,
            "created": True,
        })

    except Exception as e:
        logger.error("Failed to create collection", name=name, error=str(e))
        raise


async def list_collections() -> str:
    """List all collections."""
    try:
        collections = qdrant_client.get_collections()

        collection_info = []
        for collection in collections.collections:
            info = qdrant_client.get_collection(collection.name)
            collection_info.append({
                "name": collection.name,
                "vectors_count": info.vectors_count,
                "indexed_vectors_count": info.indexed_vectors_count,
                "points_count": info.points_count,
                "status": info.status,
            })

        return json.dumps({
            "collections": collection_info,
            "count": len(collection_info),
        })

    except Exception as e:
        logger.error("Failed to list collections", error=str(e))
        raise


async def upsert_vectors(collection: str, points: list[dict[str, Any]]) -> str:
    """Upsert vectors to a collection."""
    try:
        # Convert points to Qdrant format
        qdrant_points = []
        for point in points:
            qdrant_point = models.PointStruct(
                id=point["id"],
                vector=point["vector"],
                payload=point.get("payload", {}),
            )
            qdrant_points.append(qdrant_point)

        # Upsert points
        qdrant_client.upsert(
            collection_name=collection,
            points=qdrant_points,
        )

        logger.info("Vectors upserted", collection=collection, count=len(points))

        return json.dumps({
            "collection": collection,
            "upserted_count": len(points),
            "status": "success",
        })

    except Exception as e:
        logger.error("Failed to upsert vectors", collection=collection, error=str(e))
        raise


async def search_vectors(
    collection: str,
    query_vector: list[float],
    limit: int = 10,
    score_threshold: float | None = None,
) -> str:
    """Search for similar vectors."""
    try:
        # Build search parameters
        search_params = {
            "collection_name": collection,
            "query_vector": query_vector,
            "limit": limit,
        }

        if score_threshold is not None:
            search_params["score_threshold"] = score_threshold

        # Search
        results = qdrant_client.search(**search_params)

        # Format results
        formatted_results = []
        for result in results:
            formatted_results.append({
                "id": result.id,
                "score": result.score,
                "payload": result.payload,
            })

        return json.dumps({
            "collection": collection,
            "query_vector": query_vector,
            "results": formatted_results,
            "count": len(formatted_results),
        })

    except Exception as e:
        logger.error("Failed to search vectors", collection=collection, error=str(e))
        raise


async def search_by_text(
    collection: str,
    query_text: str,
    limit: int = 10,
    score_threshold: float | None = None,
) -> str:
    """Search for similar vectors using text query."""
    try:
        # Generate embedding for query text
        query_vector = await embedding_service.embed_text(query_text)

        # Search using the embedding
        return await search_vectors(collection, query_vector, limit, score_threshold)

    except Exception as e:
        logger.error("Failed to search by text", collection=collection, query=query_text, error=str(e))
        raise


async def delete_vectors(collection: str, ids: list[str | int]) -> str:
    """Delete vectors from a collection."""
    try:
        # Delete points
        qdrant_client.delete(
            collection_name=collection,
            points_selector=models.PointIdsList(points=ids),
        )

        logger.info("Vectors deleted", collection=collection, count=len(ids))

        return json.dumps({
            "collection": collection,
            "deleted_ids": ids,
            "deleted_count": len(ids),
            "status": "success",
        })

    except Exception as e:
        logger.error("Failed to delete vectors", collection=collection, error=str(e))
        raise


async def get_collection_info(collection: str) -> str:
    """Get information about a collection."""
    try:
        info = qdrant_client.get_collection(collection)

        return json.dumps({
            "name": collection,
            "vectors_count": info.vectors_count,
            "indexed_vectors_count": info.indexed_vectors_count,
            "points_count": info.points_count,
            "status": info.status,
            "config": {
                "vector_size": info.config.params.vectors.size,
                "distance": info.config.params.vectors.distance,
            },
        })

    except Exception as e:
        logger.error("Failed to get collection info", collection=collection, error=str(e))
        raise


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=7003)
