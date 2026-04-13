"""
Example Per-Repo MCP Server
Custom code indexer and project-specific tools for agent orchestration.
"""

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .code_indexer import CodeIndexer
from .dependency_analyzer import DependencyAnalyzer
from .project_analyzer import ProjectAnalyzer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Example Repo MCP Server",
    description="Custom code indexer and project-specific tools",
    version="0.1.0",
)

# Global instances
code_indexer: CodeIndexer | None = None
dependency_analyzer: DependencyAnalyzer | None = None
project_analyzer: ProjectAnalyzer | None = None


class IndexRequest(BaseModel):
    """Request to index a codebase."""

    path: str = Field(..., description="Path to the codebase to index")
    languages: list[str] = Field(
        default=["python", "javascript", "typescript"], description="Languages to index"
    )
    include_tests: bool = Field(default=True, description="Include test files in index")


class SearchRequest(BaseModel):
    """Request to search the codebase."""

    query: str = Field(..., description="Search query")
    file_types: list[str] | None = Field(
        default=None, description="File types to search in"
    )
    max_results: int = Field(default=10, description="Maximum number of results")


class DependencyRequest(BaseModel):
    """Request to analyze dependencies."""

    path: str = Field(..., description="Path to analyze dependencies for")


class ProjectInfoRequest(BaseModel):
    """Request to get project information."""

    path: str = Field(..., description="Path to the project")


@app.on_event("startup")
async def startup_event():
    """Initialize MCP server components."""
    global code_indexer, dependency_analyzer, project_analyzer

    logger.info("Initializing Example Repo MCP Server...")

    code_indexer = CodeIndexer()
    dependency_analyzer = DependencyAnalyzer()
    project_analyzer = ProjectAnalyzer()

    logger.info("Example Repo MCP Server initialized successfully")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "example-repo-mcp"}


@app.post("/index")
async def index_codebase(request: IndexRequest):
    """Index a codebase for search and analysis."""
    try:
        if not code_indexer:
            raise HTTPException(status_code=500, detail="Code indexer not initialized")

        path = Path(request.path)
        if not path.exists():
            raise HTTPException(
                status_code=404, detail=f"Path not found: {request.path}"
            )

        logger.info(f"Indexing codebase at {request.path}")

        # Index the codebase
        index_result = await code_indexer.index_codebase(
            path=path, languages=request.languages, include_tests=request.include_tests
        )

        return {
            "status": "success",
            "indexed_files": index_result["files_count"],
            "languages": index_result["languages"],
            "index_size": index_result["index_size"],
        }

    except Exception as e:
        logger.error(f"Error indexing codebase: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/search")
async def search_codebase(request: SearchRequest):
    """Search the indexed codebase."""
    try:
        if not code_indexer:
            raise HTTPException(status_code=500, detail="Code indexer not initialized")

        logger.info(f"Searching codebase for: {request.query}")

        # Search the codebase
        results = await code_indexer.search(
            query=request.query,
            file_types=request.file_types,
            max_results=request.max_results,
        )

        return {
            "status": "success",
            "query": request.query,
            "results": results,
            "total_results": len(results),
        }

    except Exception as e:
        logger.error(f"Error searching codebase: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/analyze-dependencies")
async def analyze_dependencies(request: DependencyRequest):
    """Analyze project dependencies."""
    try:
        if not dependency_analyzer:
            raise HTTPException(
                status_code=500, detail="Dependency analyzer not initialized"
            )

        path = Path(request.path)
        if not path.exists():
            raise HTTPException(
                status_code=404, detail=f"Path not found: {request.path}"
            )

        logger.info(f"Analyzing dependencies for {request.path}")

        # Analyze dependencies
        analysis = await dependency_analyzer.analyze_dependencies(path)

        return {
            "status": "success",
            "path": request.path,
            "dependencies": analysis["dependencies"],
            "dependency_graph": analysis["graph"],
            "vulnerabilities": analysis.get("vulnerabilities", []),
            "outdated": analysis.get("outdated", []),
        }

    except Exception as e:
        logger.error(f"Error analyzing dependencies: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/project-info")
async def get_project_info(request: ProjectInfoRequest):
    """Get comprehensive project information."""
    try:
        if not project_analyzer:
            raise HTTPException(
                status_code=500, detail="Project analyzer not initialized"
            )

        path = Path(request.path)
        if not path.exists():
            raise HTTPException(
                status_code=404, detail=f"Path not found: {request.path}"
            )

        logger.info(f"Analyzing project at {request.path}")

        # Analyze project
        project_info = await project_analyzer.analyze_project(path)

        return {"status": "success", "path": request.path, "project_info": project_info}

    except Exception as e:
        logger.error(f"Error analyzing project: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/stats")
async def get_stats():
    """Get MCP server statistics."""
    try:
        stats = {"service": "example-repo-mcp", "version": "0.1.0", "status": "running"}

        if code_indexer:
            stats["indexer"] = await code_indexer.get_stats()

        if dependency_analyzer:
            stats["dependency_analyzer"] = await dependency_analyzer.get_stats()

        if project_analyzer:
            stats["project_analyzer"] = await project_analyzer.get_stats()

        return stats

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


def main():
    """Main entry point for the MCP server."""
    import uvicorn

    uvicorn.run(
        "src.mcp_server:app", host="0.0.0.0", port=7004, reload=True, log_level="info"
    )


if __name__ == "__main__":
    main()
