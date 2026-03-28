"""Code analysis for the filesystem MCP server."""

import ast
import json
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()


class CodeAnalyzer:
    """Code analysis utilities."""

    def __init__(self):
        """Initialize code analyzer."""
        self.supported_languages = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c",
            ".hpp": "cpp",
        }

    def _detect_language(self, file_path: Path) -> str | None:
        """Detect programming language from file extension."""
        suffix = file_path.suffix.lower()
        return self.supported_languages.get(suffix)

    async def analyze_code(
        self,
        path: str,
        language: str | None = None,
        include_ast: bool = False
    ) -> dict[str, Any]:
        """Analyze code structure and dependencies."""
        try:
            file_path = Path(path)

            if not file_path.exists():
                raise FileNotFoundError(f"Path not found: {path}")

            if file_path.is_file():
                return await self._analyze_file(file_path, language, include_ast)
            elif file_path.is_dir():
                return await self._analyze_directory(file_path, language, include_ast)
            else:
                raise ValueError(f"Path is neither file nor directory: {path}")

        except Exception as e:
            logger.error("Failed to analyze code", path=path, error=str(e))
            raise

    async def _analyze_file(
        self,
        file_path: Path,
        language: str | None = None,
        include_ast: bool = False
    ) -> dict[str, Any]:
        """Analyze a single file."""
        detected_language = language or self._detect_language(file_path)

        if not detected_language:
            return {
                "path": str(file_path),
                "type": "file",
                "language": None,
                "error": "Unsupported file type",
            }

        analysis = {
            "path": str(file_path),
            "type": "file",
            "language": detected_language,
            "size": file_path.stat().st_size,
        }

        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()

            analysis["lines"] = len(content.splitlines())
            analysis["characters"] = len(content)

            if detected_language == "python":
                analysis.update(await self._analyze_python(content, include_ast))
            elif detected_language in ["javascript", "typescript"]:
                analysis.update(await self._analyze_javascript(content, include_ast))
            else:
                analysis["analysis"] = "Basic analysis only"

        except Exception as e:
            analysis["error"] = str(e)

        return analysis

    async def _analyze_python(self, content: str, include_ast: bool = False) -> dict[str, Any]:
        """Analyze Python code."""
        try:
            tree = ast.parse(content)

            analysis = {
                "imports": [],
                "functions": [],
                "classes": [],
                "variables": [],
            }

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        analysis["imports"].append({
                            "type": "import",
                            "module": alias.name,
                            "alias": alias.asname,
                        })
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        analysis["imports"].append({
                            "type": "from_import",
                            "module": node.module,
                            "name": alias.name,
                            "alias": alias.asname,
                        })
                elif isinstance(node, ast.FunctionDef):
                    analysis["functions"].append({
                        "name": node.name,
                        "line": node.lineno,
                        "args": [arg.arg for arg in node.args.args],
                        "decorators": [d.id if hasattr(d, 'id') else str(d) for d in node.decorator_list],
                    })
                elif isinstance(node, ast.ClassDef):
                    analysis["classes"].append({
                        "name": node.name,
                        "line": node.lineno,
                        "bases": [base.id if hasattr(base, 'id') else str(base) for base in node.bases],
                        "decorators": [d.id if hasattr(d, 'id') else str(d) for d in node.decorator_list],
                    })
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            analysis["variables"].append({
                                "name": target.id,
                                "line": node.lineno,
                            })

            if include_ast:
                analysis["ast"] = ast.dump(tree)

            return analysis

        except SyntaxError as e:
            return {"error": f"Syntax error: {e}"}
        except Exception as e:
            return {"error": f"Analysis error: {e}"}

    async def _analyze_javascript(self, content: str, include_ast: bool = False) -> dict[str, Any]:
        """Analyze JavaScript/TypeScript code (basic analysis)."""
        import re

        analysis = {
            "imports": [],
            "functions": [],
            "classes": [],
            "variables": [],
        }

        lines = content.splitlines()

        for i, line in enumerate(lines, 1):
            line = line.strip()

            # Import statements
            if line.startswith("import "):
                analysis["imports"].append({
                    "type": "import",
                    "line": i,
                    "statement": line,
                })
            elif line.startswith("require("):
                analysis["imports"].append({
                    "type": "require",
                    "line": i,
                    "statement": line,
                })

            # Function declarations
            func_match = re.match(r"function\s+(\w+)\s*\(", line)
            if func_match:
                analysis["functions"].append({
                    "name": func_match.group(1),
                    "line": i,
                    "type": "function",
                })

            # Arrow functions
            arrow_match = re.match(r"(\w+)\s*=\s*\([^)]*\)\s*=>", line)
            if arrow_match:
                analysis["functions"].append({
                    "name": arrow_match.group(1),
                    "line": i,
                    "type": "arrow_function",
                })

            # Class declarations
            class_match = re.match(r"class\s+(\w+)", line)
            if class_match:
                analysis["classes"].append({
                    "name": class_match.group(1),
                    "line": i,
                })

            # Variable declarations
            var_match = re.match(r"(const|let|var)\s+(\w+)", line)
            if var_match:
                analysis["variables"].append({
                    "name": var_match.group(2),
                    "line": i,
                    "type": var_match.group(1),
                })

        return analysis

    async def _analyze_directory(
        self,
        dir_path: Path,
        language: str | None = None,
        include_ast: bool = False
    ) -> dict[str, Any]:
        """Analyze all files in a directory."""
        analysis = {
            "path": str(dir_path),
            "type": "directory",
            "files": [],
            "summary": {
                "total_files": 0,
                "languages": {},
                "total_lines": 0,
                "total_functions": 0,
                "total_classes": 0,
            },
        }

        for file_path in dir_path.rglob("*"):
            if not file_path.is_file():
                continue

            # Skip hidden files and common non-code files
            if file_path.name.startswith(".") or file_path.suffix in [".pyc", ".pyo", "__pycache__"]:
                continue

            file_language = language or self._detect_language(file_path)
            if not file_language:
                continue

            try:
                file_analysis = await self._analyze_file(file_path, file_language, include_ast)
                analysis["files"].append(file_analysis)

                # Update summary
                analysis["summary"]["total_files"] += 1
                analysis["summary"]["languages"][file_language] = analysis["summary"]["languages"].get(file_language, 0) + 1
                analysis["summary"]["total_lines"] += file_analysis.get("lines", 0)
                analysis["summary"]["total_functions"] += len(file_analysis.get("functions", []))
                analysis["summary"]["total_classes"] += len(file_analysis.get("classes", []))

            except Exception as e:
                logger.warning("Failed to analyze file", file=str(file_path), error=str(e))
                continue

        return analysis

    async def get_dependencies(self, path: str, language: str | None = None) -> dict[str, Any]:
        """Get dependencies for a project."""
        try:
            project_path = Path(path)

            if not project_path.exists():
                raise FileNotFoundError(f"Project path not found: {path}")

            if not project_path.is_dir():
                raise ValueError(f"Project path is not a directory: {path}")

            dependencies = {
                "path": str(project_path),
                "language": language,
                "dependencies": [],
                "dev_dependencies": [],
                "files_found": [],
            }

            # Python dependencies
            if language == "python" or (project_path / "requirements.txt").exists():
                deps = await self._get_python_dependencies(project_path)
                dependencies.update(deps)
                dependencies["language"] = "python"

            # Node.js dependencies
            elif language == "javascript" or language == "typescript" or (project_path / "package.json").exists():
                deps = await self._get_node_dependencies(project_path)
                dependencies.update(deps)
                dependencies["language"] = "javascript"

            # Go dependencies
            elif language == "go" or (project_path / "go.mod").exists():
                deps = await self._get_go_dependencies(project_path)
                dependencies.update(deps)
                dependencies["language"] = "go"

            # Rust dependencies
            elif language == "rust" or (project_path / "Cargo.toml").exists():
                deps = await self._get_rust_dependencies(project_path)
                dependencies.update(deps)
                dependencies["language"] = "rust"

            return dependencies

        except Exception as e:
            logger.error("Failed to get dependencies", path=path, error=str(e))
            raise

    async def _get_python_dependencies(self, project_path: Path) -> dict[str, Any]:
        """Get Python dependencies."""
        dependencies = {
            "dependencies": [],
            "dev_dependencies": [],
            "files_found": [],
        }

        # requirements.txt
        req_file = project_path / "requirements.txt"
        if req_file.exists():
            dependencies["files_found"].append("requirements.txt")
            with open(req_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        dependencies["dependencies"].append(line)

        # pyproject.toml
        pyproject_file = project_path / "pyproject.toml"
        if pyproject_file.exists():
            dependencies["files_found"].append("pyproject.toml")
            # Basic parsing - in production, use tomllib or toml
            with open(pyproject_file) as f:
                content = f.read()
                # Simple regex to find dependencies
                import re
                deps_match = re.search(r'\[project\]\s*dependencies\s*=\s*\[(.*?)\]', content, re.DOTALL)
                if deps_match:
                    deps_text = deps_match.group(1)
                    for dep in re.findall(r'"([^"]+)"', deps_text):
                        dependencies["dependencies"].append(dep)

        return dependencies

    async def _get_node_dependencies(self, project_path: Path) -> dict[str, Any]:
        """Get Node.js dependencies."""
        dependencies = {
            "dependencies": [],
            "dev_dependencies": [],
            "files_found": [],
        }

        package_file = project_path / "package.json"
        if package_file.exists():
            dependencies["files_found"].append("package.json")
            try:
                with open(package_file) as f:
                    package_data = json.load(f)

                dependencies["dependencies"] = list(package_data.get("dependencies", {}).keys())
                dependencies["dev_dependencies"] = list(package_data.get("devDependencies", {}).keys())

            except json.JSONDecodeError as e:
                dependencies["error"] = f"Failed to parse package.json: {e}"

        return dependencies

    async def _get_go_dependencies(self, project_path: Path) -> dict[str, Any]:
        """Get Go dependencies."""
        dependencies = {
            "dependencies": [],
            "files_found": [],
        }

        go_mod_file = project_path / "go.mod"
        if go_mod_file.exists():
            dependencies["files_found"].append("go.mod")
            with open(go_mod_file) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("require ") and not line.startswith("require ("):
                        # Single require
                        dep = line.split()[1]
                        dependencies["dependencies"].append(dep)
                    elif line.startswith("require ("):
                        # Multi-line require block
                        continue
                    elif line and not line.startswith("module ") and not line.startswith("go "):
                        # Dependency in multi-line block
                        dep = line.split()[0]
                        if dep and not dep.startswith(")"):
                            dependencies["dependencies"].append(dep)

        return dependencies

    async def _get_rust_dependencies(self, project_path: Path) -> dict[str, Any]:
        """Get Rust dependencies."""
        dependencies = {
            "dependencies": [],
            "dev_dependencies": [],
            "files_found": [],
        }

        cargo_file = project_path / "Cargo.toml"
        if cargo_file.exists():
            dependencies["files_found"].append("Cargo.toml")
            with open(cargo_file) as f:
                content = f.read()

                # Simple parsing - in production, use toml library
                import re

                # Find [dependencies] section
                deps_match = re.search(r'\[dependencies\]\s*(.*?)(?=\[|$)', content, re.DOTALL)
                if deps_match:
                    deps_text = deps_match.group(1)
                    for line in deps_text.splitlines():
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            dep_name = line.split("=")[0].strip()
                            dependencies["dependencies"].append(dep_name)

                # Find [dev-dependencies] section
                dev_deps_match = re.search(r'\[dev-dependencies\]\s*(.*?)(?=\[|$)', content, re.DOTALL)
                if dev_deps_match:
                    dev_deps_text = dev_deps_match.group(1)
                    for line in dev_deps_text.splitlines():
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            dep_name = line.split("=")[0].strip()
                            dependencies["dev_dependencies"].append(dep_name)

        return dependencies
