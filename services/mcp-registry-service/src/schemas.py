"""JSON Schema definitions for MCP tools and resources."""

from typing import Any

from pydantic import BaseModel, Field


class MCPSchema(BaseModel):
    """Base MCP schema definition."""

    name: str = Field(..., description="Schema name")
    version: str = Field(..., description="Schema version")
    description: str = Field(..., description="Schema description")
    type: str = Field(..., description="Schema type (tool|resource)")


class ToolSchema(MCPSchema):
    """Tool schema definition."""

    type: str = Field(default="tool", description="Schema type")
    parameters: dict[str, Any] = Field(..., description="Tool parameters schema")
    returns: dict[str, Any] = Field(..., description="Tool return value schema")
    examples: list[dict[str, Any]] = Field(
        default_factory=list, description="Usage examples"
    )


class ResourceSchema(MCPSchema):
    """Resource schema definition."""

    type: str = Field(default="resource", description="Schema type")
    content_type: str = Field(..., description="Resource content type")
    metadata_schema: dict[str, Any] = Field(..., description="Resource metadata schema")
    access_methods: list[str] = Field(..., description="Available access methods")
    examples: list[dict[str, Any]] = Field(
        default_factory=list, description="Usage examples"
    )


# Predefined schemas for common MCP types
GITHUB_TOOL_SCHEMA = ToolSchema(
    name="github_tool",
    version="1.0.0",
    description="GitHub operations tool",
    parameters={
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["create_issue", "create_pr", "get_repo", "list_issues"],
                "description": "GitHub operation to perform",
            },
            "repository": {
                "type": "string",
                "description": "Repository name (owner/repo)",
            },
            "title": {"type": "string", "description": "Issue or PR title"},
            "body": {"type": "string", "description": "Issue or PR body content"},
            "labels": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Labels to apply",
            },
        },
        "required": ["operation", "repository"],
    },
    returns={
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "url": {"type": "string"},
            "id": {"type": "integer"},
            "message": {"type": "string"},
        },
    },
    examples=[
        {
            "operation": "create_issue",
            "repository": "owner/repo",
            "title": "Bug report",
            "body": "Description of the bug",
            "labels": ["bug", "priority-high"],
        }
    ],
)

FILESYSTEM_TOOL_SCHEMA = ToolSchema(
    name="filesystem_tool",
    version="1.0.0",
    description="Filesystem operations tool",
    parameters={
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["read", "write", "list", "delete", "copy", "move"],
                "description": "Filesystem operation to perform",
            },
            "path": {"type": "string", "description": "File or directory path"},
            "content": {
                "type": "string",
                "description": "Content to write (for write operations)",
            },
            "destination": {
                "type": "string",
                "description": "Destination path (for copy/move operations)",
            },
        },
        "required": ["operation", "path"],
    },
    returns={
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "content": {"type": "string"},
            "files": {"type": "array", "items": {"type": "string"}},
            "message": {"type": "string"},
        },
    },
    examples=[
        {"operation": "read", "path": "/path/to/file.txt"},
        {"operation": "write", "path": "/path/to/file.txt", "content": "File content"},
    ],
)

CODE_RESOURCE_SCHEMA = ResourceSchema(
    name="code_resource",
    version="1.0.0",
    description="Code repository resource",
    content_type="text/plain",
    metadata_schema={
        "type": "object",
        "properties": {
            "repository": {"type": "string"},
            "file_path": {"type": "string"},
            "commit_sha": {"type": "string"},
            "line_start": {"type": "integer"},
            "line_end": {"type": "integer"},
            "language": {"type": "string"},
            "function_name": {"type": "string"},
            "class_name": {"type": "string"},
        },
    },
    access_methods=["search", "retrieve", "embed"],
    examples=[
        {
            "repository": "owner/repo",
            "file_path": "src/main.py",
            "commit_sha": "abc123",
            "line_start": 10,
            "line_end": 20,
            "language": "python",
            "function_name": "main",
        }
    ],
)

DOCUMENT_RESOURCE_SCHEMA = ResourceSchema(
    name="document_resource",
    version="1.0.0",
    description="Document resource",
    content_type="text/plain",
    metadata_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "author": {"type": "string"},
            "publisher": {"type": "string"},
            "publication_date": {"type": "string"},
            "isbn": {"type": "string"},
            "doi": {"type": "string"},
            "page_number": {"type": "integer"},
            "section": {"type": "string"},
            "chapter": {"type": "string"},
            "content_sha256": {"type": "string"},
        },
    },
    access_methods=["search", "retrieve", "embed"],
    examples=[
        {
            "title": "Engineering Design Principles",
            "author": "John Smith",
            "publisher": "Engineering Press",
            "publication_date": "2023-01-01",
            "isbn": "978-0-123456-78-9",
            "page_number": 45,
            "section": "Chapter 3: Materials Selection",
        }
    ],
)

CHEMISTRY_TOOL_SCHEMA = ToolSchema(
    name="chemistry_tool",
    version="1.0.0",
    description="Chemistry calculations and analysis tool",
    parameters={
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": [
                    "molecular_weight",
                    "stoichiometry",
                    "concentration",
                    "ph_calculation",
                ],
                "description": "Chemistry operation to perform",
            },
            "formula": {"type": "string", "description": "Chemical formula"},
            "concentration": {"type": "number", "description": "Concentration value"},
            "volume": {"type": "number", "description": "Volume in liters"},
            "moles": {"type": "number", "description": "Number of moles"},
        },
        "required": ["operation"],
    },
    returns={
        "type": "object",
        "properties": {
            "result": {"type": "number"},
            "unit": {"type": "string"},
            "formula": {"type": "string"},
            "calculation": {"type": "string"},
        },
    },
    examples=[
        {"operation": "molecular_weight", "formula": "H2O"},
        {"operation": "concentration", "moles": 0.1, "volume": 0.5},
    ],
)

MECHANICAL_TOOL_SCHEMA = ToolSchema(
    name="mechanical_tool",
    version="1.0.0",
    description="Mechanical engineering calculations tool",
    parameters={
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["stress_calculation", "deflection", "torque", "gear_ratio"],
                "description": "Mechanical operation to perform",
            },
            "force": {"type": "number", "description": "Force value in Newtons"},
            "area": {"type": "number", "description": "Cross-sectional area in m²"},
            "length": {"type": "number", "description": "Length in meters"},
            "modulus": {"type": "number", "description": "Elastic modulus in Pa"},
            "moment": {"type": "number", "description": "Moment of inertia in m⁴"},
        },
        "required": ["operation"],
    },
    returns={
        "type": "object",
        "properties": {
            "result": {"type": "number"},
            "unit": {"type": "string"},
            "formula": {"type": "string"},
            "calculation": {"type": "string"},
        },
    },
    examples=[
        {"operation": "stress_calculation", "force": 1000, "area": 0.01},
        {
            "operation": "deflection",
            "force": 1000,
            "length": 2.0,
            "modulus": 200e9,
            "moment": 0.001,
        },
    ],
)

MATERIALS_TOOL_SCHEMA = ToolSchema(
    name="materials_tool",
    version="1.0.0",
    description="Materials engineering tool",
    parameters={
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["property_lookup", "alloy_composition", "heat_treatment"],
                "description": "Materials operation to perform",
            },
            "material": {
                "type": "string",
                "description": "Material name or alloy designation",
            },
            "property": {
                "type": "string",
                "enum": ["yield_strength", "tensile_strength", "hardness", "density"],
                "description": "Property to look up",
            },
            "temperature": {"type": "number", "description": "Temperature in °C"},
            "composition": {
                "type": "object",
                "description": "Alloy composition percentages",
            },
        },
        "required": ["operation", "material"],
    },
    returns={
        "type": "object",
        "properties": {
            "value": {"type": "number"},
            "unit": {"type": "string"},
            "temperature": {"type": "number"},
            "source": {"type": "string"},
            "notes": {"type": "string"},
        },
    },
    examples=[
        {
            "operation": "property_lookup",
            "material": "AISI 316L",
            "property": "yield_strength",
        },
        {
            "operation": "alloy_composition",
            "material": "304 Stainless Steel",
            "composition": {"Fe": 70, "Cr": 18, "Ni": 8, "C": 0.08},
        },
    ],
)


# Schema registry
SCHEMA_REGISTRY = {
    "github_tool": GITHUB_TOOL_SCHEMA,
    "filesystem_tool": FILESYSTEM_TOOL_SCHEMA,
    "code_resource": CODE_RESOURCE_SCHEMA,
    "document_resource": DOCUMENT_RESOURCE_SCHEMA,
    "chemistry_tool": CHEMISTRY_TOOL_SCHEMA,
    "mechanical_tool": MECHANICAL_TOOL_SCHEMA,
    "materials_tool": MATERIALS_TOOL_SCHEMA,
}


def get_schema(schema_name: str) -> MCPSchema | None:
    """Get schema by name.

    Args:
        schema_name: Schema name

    Returns:
        Schema or None if not found
    """
    return SCHEMA_REGISTRY.get(schema_name)


def list_schemas() -> list[str]:
    """List all available schema names.

    Returns:
        List of schema names
    """
    return list(SCHEMA_REGISTRY.keys())


def get_schemas_by_type(schema_type: str) -> list[MCPSchema]:
    """Get schemas by type.

    Args:
        schema_type: Schema type (tool|resource)

    Returns:
        List of schemas of the specified type
    """
    return [schema for schema in SCHEMA_REGISTRY.values() if schema.type == schema_type]
