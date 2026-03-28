"""
Dependency Analyzer for Per-Repo MCP Server
Analyzes project dependencies and their relationships.
"""

import json
import logging
from pathlib import Path
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)


class DependencyAnalyzer:
    """Analyzes project dependencies and their relationships."""

    def __init__(self):
        self.dependency_graph = nx.DiGraph()
        self.vulnerability_db = {}  # Placeholder for vulnerability database

    async def analyze_dependencies(self, path: Path) -> dict[str, Any]:
        """Analyze dependencies for a project."""
        logger.info(f"Analyzing dependencies for {path}")

        # Detect project type and load dependencies
        project_type = self._detect_project_type(path)
        dependencies = await self._load_dependencies(path, project_type)

        # Build dependency graph
        self._build_dependency_graph(dependencies, project_type)

        # Analyze for issues
        vulnerabilities = await self._check_vulnerabilities(dependencies)
        outdated = await self._check_outdated(dependencies)

        return {
            "project_type": project_type,
            "dependencies": dependencies,
            "graph": self._graph_to_dict(),
            "vulnerabilities": vulnerabilities,
            "outdated": outdated,
            "stats": self._get_dependency_stats()
        }

    def _detect_project_type(self, path: Path) -> str:
        """Detect the type of project (Python, Node.js, etc.)."""
        if (path / "pyproject.toml").exists() or (path / "requirements.txt").exists():
            return "python"
        elif (path / "package.json").exists():
            return "nodejs"
        elif (path / "Cargo.toml").exists():
            return "rust"
        elif (path / "go.mod").exists():
            return "go"
        else:
            return "unknown"

    async def _load_dependencies(self, path: Path, project_type: str) -> dict[str, Any]:
        """Load dependencies based on project type."""
        dependencies = {}

        if project_type == "python":
            dependencies = await self._load_python_dependencies(path)
        elif project_type == "nodejs":
            dependencies = await self._load_nodejs_dependencies(path)
        elif project_type == "rust":
            dependencies = await self._load_rust_dependencies(path)
        elif project_type == "go":
            dependencies = await self._load_go_dependencies(path)

        return dependencies

    async def _load_python_dependencies(self, path: Path) -> dict[str, Any]:
        """Load Python dependencies from pyproject.toml or requirements.txt."""
        dependencies = {}

        # Try pyproject.toml first
        pyproject_path = path / "pyproject.toml"
        if pyproject_path.exists():
            try:
                import tomllib
                with open(pyproject_path, 'rb') as f:
                    data = tomllib.load(f)

                # Extract dependencies
                deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
                for name, version in deps.items():
                    if name != "python":
                        dependencies[name] = {
                            "version": str(version),
                            "type": "runtime"
                        }

                # Extract dev dependencies
                dev_deps = data.get("tool", {}).get("poetry", {}).get("group", {}).get("dev", {}).get("dependencies", {})
                for name, version in dev_deps.items():
                    dependencies[name] = {
                        "version": str(version),
                        "type": "dev"
                    }

            except Exception as e:
                logger.warning(f"Failed to parse pyproject.toml: {e}")

        # Fallback to requirements.txt
        if not dependencies:
            req_path = path / "requirements.txt"
            if req_path.exists():
                try:
                    with open(req_path) as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                # Parse requirement line
                                if '==' in line:
                                    name, version = line.split('==', 1)
                                    dependencies[name.strip()] = {
                                        "version": version.strip(),
                                        "type": "runtime"
                                    }
                                elif '>=' in line:
                                    name, version = line.split('>=', 1)
                                    dependencies[name.strip()] = {
                                        "version": f">={version.strip()}",
                                        "type": "runtime"
                                    }
                except Exception as e:
                    logger.warning(f"Failed to parse requirements.txt: {e}")

        return dependencies

    async def _load_nodejs_dependencies(self, path: Path) -> dict[str, Any]:
        """Load Node.js dependencies from package.json."""
        dependencies = {}

        package_path = path / "package.json"
        if package_path.exists():
            try:
                with open(package_path) as f:
                    data = json.load(f)

                # Extract dependencies
                deps = data.get("dependencies", {})
                for name, version in deps.items():
                    dependencies[name] = {
                        "version": version,
                        "type": "runtime"
                    }

                # Extract dev dependencies
                dev_deps = data.get("devDependencies", {})
                for name, version in dev_deps.items():
                    dependencies[name] = {
                        "version": version,
                        "type": "dev"
                    }

            except Exception as e:
                logger.warning(f"Failed to parse package.json: {e}")

        return dependencies

    async def _load_rust_dependencies(self, path: Path) -> dict[str, Any]:
        """Load Rust dependencies from Cargo.toml."""
        dependencies = {}

        cargo_path = path / "Cargo.toml"
        if cargo_path.exists():
            try:
                import tomllib
                with open(cargo_path, 'rb') as f:
                    data = tomllib.load(f)

                # Extract dependencies
                deps = data.get("dependencies", {})
                for name, version in deps.items():
                    if isinstance(version, str):
                        dependencies[name] = {
                            "version": version,
                            "type": "runtime"
                        }
                    elif isinstance(version, dict):
                        dependencies[name] = {
                            "version": version.get("version", "*"),
                            "type": "runtime"
                        }

            except Exception as e:
                logger.warning(f"Failed to parse Cargo.toml: {e}")

        return dependencies

    async def _load_go_dependencies(self, path: Path) -> dict[str, Any]:
        """Load Go dependencies from go.mod."""
        dependencies = {}

        go_mod_path = path / "go.mod"
        if go_mod_path.exists():
            try:
                with open(go_mod_path) as f:
                    lines = f.readlines()

                in_require_section = False
                for line in lines:
                    line = line.strip()
                    if line == "require (":
                        in_require_section = True
                        continue
                    elif line == ")":
                        in_require_section = False
                        continue
                    elif in_require_section and line:
                        # Parse require line
                        parts = line.split()
                        if len(parts) >= 2:
                            name = parts[0]
                            version = parts[1]
                            dependencies[name] = {
                                "version": version,
                                "type": "runtime"
                            }

            except Exception as e:
                logger.warning(f"Failed to parse go.mod: {e}")

        return dependencies

    def _build_dependency_graph(self, dependencies: dict[str, Any], project_type: str):
        """Build a dependency graph from the dependencies."""
        self.dependency_graph.clear()

        # Add all dependencies as nodes
        for name, info in dependencies.items():
            self.dependency_graph.add_node(name, **info)

        # Add edges based on dependency relationships
        # This is a simplified version - in reality, you'd need to resolve
        # transitive dependencies by analyzing the actual dependency tree
        for _name, _info in dependencies.items():
            # Add edges to direct dependencies (simplified)
            # In a real implementation, you'd parse the dependency tree
            pass

    def _graph_to_dict(self) -> dict[str, Any]:
        """Convert networkx graph to dictionary for JSON serialization."""
        return {
            "nodes": list(self.dependency_graph.nodes()),
            "edges": list(self.dependency_graph.edges()),
            "node_data": dict(self.dependency_graph.nodes(data=True))
        }

    async def _check_vulnerabilities(self, dependencies: dict[str, Any]) -> list[dict[str, Any]]:
        """Check for known vulnerabilities in dependencies."""
        # This is a placeholder - in a real implementation, you'd integrate
        # with vulnerability databases like OSV, Snyk, or GitHub Security Advisories
        vulnerabilities = []

        # Example vulnerability check (placeholder)
        for name, info in dependencies.items():
            if name in self.vulnerability_db:
                vulnerabilities.append({
                    "package": name,
                    "version": info["version"],
                    "vulnerability": self.vulnerability_db[name],
                    "severity": "high"
                })

        return vulnerabilities

    async def _check_outdated(self, dependencies: dict[str, Any]) -> list[dict[str, Any]]:
        """Check for outdated dependencies."""
        # This is a placeholder - in a real implementation, you'd check
        # against package registries (PyPI, npm, crates.io, etc.)
        outdated = []

        # Example outdated check (placeholder)
        for name, info in dependencies.items():
            # Simulate checking for newer versions
            if "old" in name.lower() or "legacy" in name.lower():
                outdated.append({
                    "package": name,
                    "current_version": info["version"],
                    "latest_version": "2.0.0",
                    "type": info["type"]
                })

        return outdated

    def _get_dependency_stats(self) -> dict[str, Any]:
        """Get dependency statistics."""
        total_deps = len(self.dependency_graph.nodes())
        runtime_deps = sum(1 for node in self.dependency_graph.nodes(data=True)
                          if node[1].get("type") == "runtime")
        dev_deps = sum(1 for node in self.dependency_graph.nodes(data=True)
                      if node[1].get("type") == "dev")

        return {
            "total_dependencies": total_deps,
            "runtime_dependencies": runtime_deps,
            "dev_dependencies": dev_deps,
            "graph_nodes": self.dependency_graph.number_of_nodes(),
            "graph_edges": self.dependency_graph.number_of_edges()
        }

    async def get_stats(self) -> dict[str, Any]:
        """Get analyzer statistics."""
        return {
            "analyzed_projects": 1,  # Placeholder
            "total_dependencies": len(self.dependency_graph.nodes()),
            "vulnerability_checks": len(self.vulnerability_db)
        }
