"""
Project Analyzer for Per-Repo MCP Server
Analyzes project structure, metrics, and characteristics.
"""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ProjectAnalyzer:
    """Analyzes project structure, metrics, and characteristics."""

    def __init__(self):
        self.analysis_cache = {}

    async def analyze_project(self, path: Path) -> dict[str, Any]:
        """Perform comprehensive project analysis."""
        logger.info(f"Analyzing project at {path}")

        # Basic project info
        project_info = {
            "name": path.name,
            "path": str(path),
            "type": self._detect_project_type(path),
            "size": await self._calculate_project_size(path),
            "structure": await self._analyze_structure(path),
            "metrics": await self._calculate_metrics(path),
            "configuration": await self._analyze_configuration(path),
            "documentation": await self._analyze_documentation(path),
            "testing": await self._analyze_testing(path),
            "ci_cd": await self._analyze_ci_cd(path),
        }

        return project_info

    def _detect_project_type(self, path: Path) -> str:
        """Detect the type of project."""
        indicators = {
            "python": ["pyproject.toml", "requirements.txt", "setup.py", "Pipfile"],
            "nodejs": ["package.json", "yarn.lock", "package-lock.json"],
            "rust": ["Cargo.toml", "Cargo.lock"],
            "go": ["go.mod", "go.sum"],
            "java": ["pom.xml", "build.gradle", "gradle.properties"],
            "dotnet": ["*.csproj", "*.sln", "*.fsproj"],
            "docker": ["Dockerfile", "docker-compose.yml"],
            "terraform": ["*.tf", "*.tfvars"],
            "ansible": ["playbook.yml", "inventory.ini"],
            "kubernetes": ["*.yaml", "*.yml", "kustomization.yaml"],
        }

        detected_types = []
        for project_type, files in indicators.items():
            for file_pattern in files:
                if file_pattern.startswith("*"):
                    # Handle wildcard patterns
                    if list(path.glob(file_pattern)):
                        detected_types.append(project_type)
                else:
                    # Handle exact file names
                    if (path / file_pattern).exists():
                        detected_types.append(project_type)

        if not detected_types:
            return "unknown"
        elif len(detected_types) == 1:
            return detected_types[0]
        else:
            return f"multi-{'-'.join(detected_types)}"

    async def _calculate_project_size(self, path: Path) -> dict[str, Any]:
        """Calculate project size metrics."""
        total_files = 0
        total_size = 0
        file_types = {}

        for file_path in path.rglob("*"):
            if file_path.is_file():
                total_files += 1
                file_size = file_path.stat().st_size
                total_size += file_size

                # Count by file type
                suffix = file_path.suffix.lower()
                if suffix:
                    file_types[suffix] = file_types.get(suffix, 0) + 1
                else:
                    file_types["no_extension"] = file_types.get("no_extension", 0) + 1

        return {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "file_types": file_types,
        }

    async def _analyze_structure(self, path: Path) -> dict[str, Any]:
        """Analyze project directory structure."""
        structure = {"directories": [], "key_files": [], "depth": 0}

        # Find key directories
        key_dirs = [
            "src",
            "lib",
            "app",
            "tests",
            "test",
            "docs",
            "doc",
            "config",
            "scripts",
        ]
        for dir_name in key_dirs:
            dir_path = path / dir_name
            if dir_path.exists() and dir_path.is_dir():
                structure["directories"].append(dir_name)

        # Find key files
        key_files = [
            "README.md",
            "README.rst",
            "README.txt",
            "LICENSE",
            "LICENSE.txt",
            "LICENSE.md",
            "CHANGELOG.md",
            "CHANGELOG.rst",
            "CHANGELOG.txt",
            "CONTRIBUTING.md",
            "CONTRIBUTING.rst",
            ".gitignore",
            ".dockerignore",
            "Makefile",
            "Dockerfile",
            "docker-compose.yml",
        ]

        for file_name in key_files:
            file_path = path / file_name
            if file_path.exists():
                structure["key_files"].append(file_name)

        # Calculate max depth
        max_depth = 0
        for file_path in path.rglob("*"):
            if file_path.is_file():
                depth = len(file_path.relative_to(path).parts)
                max_depth = max(max_depth, depth)

        structure["depth"] = max_depth

        return structure

    async def _calculate_metrics(self, path: Path) -> dict[str, Any]:
        """Calculate code metrics."""
        metrics = {
            "lines_of_code": 0,
            "blank_lines": 0,
            "comment_lines": 0,
            "languages": {},
        }

        # Common code file extensions
        code_extensions = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".java": "java",
            ".cs": "csharp",
            ".go": "go",
            ".rs": "rust",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c",
            ".hpp": "cpp",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".r": "r",
            ".m": "matlab",
            ".sh": "shell",
            ".bash": "shell",
            ".zsh": "shell",
            ".fish": "shell",
            ".ps1": "powershell",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".json": "json",
            ".xml": "xml",
            ".html": "html",
            ".css": "css",
            ".scss": "scss",
            ".sass": "sass",
            ".less": "less",
            ".sql": "sql",
            ".md": "markdown",
            ".rst": "rst",
            ".tex": "latex",
        }

        for file_path in path.rglob("*"):
            if file_path.is_file():
                suffix = file_path.suffix.lower()
                if suffix in code_extensions:
                    language = code_extensions[suffix]

                    try:
                        with open(file_path, encoding="utf-8", errors="ignore") as f:
                            lines = f.readlines()

                        file_metrics = self._analyze_file_lines(lines, language)

                        if language not in metrics["languages"]:
                            metrics["languages"][language] = {
                                "files": 0,
                                "lines": 0,
                                "blank_lines": 0,
                                "comment_lines": 0,
                            }

                        metrics["languages"][language]["files"] += 1
                        metrics["languages"][language]["lines"] += file_metrics["lines"]
                        metrics["languages"][language]["blank_lines"] += file_metrics[
                            "blank_lines"
                        ]
                        metrics["languages"][language]["comment_lines"] += file_metrics[
                            "comment_lines"
                        ]

                        metrics["lines_of_code"] += file_metrics["lines"]
                        metrics["blank_lines"] += file_metrics["blank_lines"]
                        metrics["comment_lines"] += file_metrics["comment_lines"]

                    except Exception as e:
                        logger.warning(f"Failed to analyze {file_path}: {e}")
                        continue

        return metrics

    def _analyze_file_lines(self, lines: list[str], language: str) -> dict[str, int]:
        """Analyze lines in a file for metrics."""
        total_lines = len(lines)
        blank_lines = 0
        comment_lines = 0

        # Language-specific comment patterns
        comment_patterns = {
            "python": ["#"],
            "javascript": ["//", "/*", "*"],
            "typescript": ["//", "/*", "*"],
            "java": ["//", "/*", "*"],
            "csharp": ["//", "/*", "*"],
            "go": ["//", "/*", "*"],
            "rust": ["//", "/*", "*"],
            "cpp": ["//", "/*", "*"],
            "c": ["//", "/*", "*"],
            "ruby": ["#"],
            "php": ["//", "/*", "*", "#"],
            "swift": ["//", "/*", "*"],
            "kotlin": ["//", "/*", "*"],
            "scala": ["//", "/*", "*"],
            "r": ["#"],
            "shell": ["#"],
            "powershell": ["#"],
            "yaml": ["#"],
            "json": [],  # JSON doesn't have comments
            "xml": ["<!--", "-->"],
            "html": ["<!--", "-->"],
            "css": ["/*", "*"],
            "scss": ["//", "/*", "*"],
            "sass": ["//", "/*", "*"],
            "less": ["//", "/*", "*"],
            "sql": ["--", "/*", "*"],
            "markdown": [],  # Markdown doesn't have traditional comments
            "rst": [".."],
            "latex": ["%"],
        }

        patterns = comment_patterns.get(language, [])

        for line in lines:
            stripped = line.strip()

            if not stripped:
                blank_lines += 1
            else:
                # Check for comments
                is_comment = False
                for pattern in patterns:
                    if stripped.startswith(pattern):
                        is_comment = True
                        break

                if is_comment:
                    comment_lines += 1

        return {
            "lines": total_lines,
            "blank_lines": blank_lines,
            "comment_lines": comment_lines,
        }

    async def _analyze_configuration(self, path: Path) -> dict[str, Any]:
        """Analyze project configuration files."""
        config_files = {}

        # Common configuration files
        config_patterns = {
            "pyproject.toml": "python",
            "requirements.txt": "python",
            "setup.py": "python",
            "Pipfile": "python",
            "package.json": "nodejs",
            "yarn.lock": "nodejs",
            "package-lock.json": "nodejs",
            "Cargo.toml": "rust",
            "go.mod": "go",
            "pom.xml": "java",
            "build.gradle": "java",
            "*.csproj": "dotnet",
            "*.sln": "dotnet",
            "Dockerfile": "docker",
            "docker-compose.yml": "docker",
            "*.tf": "terraform",
            "*.tfvars": "terraform",
            "playbook.yml": "ansible",
            "inventory.ini": "ansible",
            "kustomization.yaml": "kubernetes",
            ".gitignore": "git",
            ".dockerignore": "docker",
            "Makefile": "make",
            ".env.example": "environment",
            ".env": "environment",
        }

        for pattern, config_type in config_patterns.items():
            if pattern.startswith("*"):
                # Handle wildcard patterns
                matches = list(path.glob(pattern))
                if matches:
                    config_files[pattern] = {
                        "type": config_type,
                        "files": [str(f.relative_to(path)) for f in matches],
                    }
            else:
                # Handle exact file names
                file_path = path / pattern
                if file_path.exists():
                    config_files[pattern] = {"type": config_type, "files": [pattern]}

        return config_files

    async def _analyze_documentation(self, path: Path) -> dict[str, Any]:
        """Analyze project documentation."""
        doc_files = []
        doc_types = {}

        # Common documentation files
        doc_patterns = [
            "README*",
            "CHANGELOG*",
            "CONTRIBUTING*",
            "LICENSE*",
            "docs/**/*",
            "doc/**/*",
            "*.md",
            "*.rst",
            "*.txt",
        ]

        for pattern in doc_patterns:
            matches = list(path.glob(pattern))
            for match in matches:
                if match.is_file():
                    doc_files.append(str(match.relative_to(path)))

                    # Categorize by type
                    if "README" in match.name:
                        doc_types["readme"] = doc_types.get("readme", 0) + 1
                    elif "CHANGELOG" in match.name:
                        doc_types["changelog"] = doc_types.get("changelog", 0) + 1
                    elif "CONTRIBUTING" in match.name:
                        doc_types["contributing"] = doc_types.get("contributing", 0) + 1
                    elif "LICENSE" in match.name:
                        doc_types["license"] = doc_types.get("license", 0) + 1
                    elif match.suffix == ".md":
                        doc_types["markdown"] = doc_types.get("markdown", 0) + 1
                    elif match.suffix == ".rst":
                        doc_types["rst"] = doc_types.get("rst", 0) + 1
                    else:
                        doc_types["other"] = doc_types.get("other", 0) + 1

        return {"files": doc_files, "types": doc_types, "total_files": len(doc_files)}

    async def _analyze_testing(self, path: Path) -> dict[str, Any]:
        """Analyze testing setup and files."""
        test_files = []
        test_frameworks = {}

        # Common test file patterns
        test_patterns = [
            "test_*.py",
            "*_test.py",
            "tests/**/*",
            "*.test.js",
            "*.test.ts",
            "*.spec.js",
            "*.spec.ts",
            "test/**/*",
            "__tests__/**/*",
            "*Test.java",
            "*Tests.java",
            "*_test.go",
            "*_test.rs",
            "*.test.cs",
            "*.Tests.cs",
        ]

        for pattern in test_patterns:
            matches = list(path.glob(pattern))
            for match in matches:
                if match.is_file():
                    test_files.append(str(match.relative_to(path)))

                    # Detect test framework
                    if match.suffix == ".py":
                        test_frameworks["pytest"] = test_frameworks.get("pytest", 0) + 1
                    elif match.suffix in [".js", ".ts"]:
                        test_frameworks["jest"] = test_frameworks.get("jest", 0) + 1
                    elif match.suffix == ".java":
                        test_frameworks["junit"] = test_frameworks.get("junit", 0) + 1
                    elif match.suffix == ".go":
                        test_frameworks["go_test"] = (
                            test_frameworks.get("go_test", 0) + 1
                        )
                    elif match.suffix == ".rs":
                        test_frameworks["cargo_test"] = (
                            test_frameworks.get("cargo_test", 0) + 1
                        )
                    elif match.suffix == ".cs":
                        test_frameworks["nunit"] = test_frameworks.get("nunit", 0) + 1

        return {
            "files": test_files,
            "frameworks": test_frameworks,
            "total_files": len(test_files),
        }

    async def _analyze_ci_cd(self, path: Path) -> dict[str, Any]:
        """Analyze CI/CD configuration."""
        ci_files = []
        ci_platforms = {}

        # Common CI/CD files
        ci_patterns = [
            ".github/workflows/*.yml",
            ".github/workflows/*.yaml",
            ".gitlab-ci.yml",
            ".gitlab-ci.yaml",
            ".travis.yml",
            ".travis.yaml",
            ".circleci/config.yml",
            ".circleci/config.yaml",
            "azure-pipelines.yml",
            "azure-pipelines.yaml",
            "Jenkinsfile",
            "Jenkinsfile.*",
            ".drone.yml",
            ".drone.yaml",
            "buildkite.yml",
            "buildkite.yaml",
        ]

        for pattern in ci_patterns:
            matches = list(path.glob(pattern))
            for match in matches:
                if match.is_file():
                    ci_files.append(str(match.relative_to(path)))

                    # Detect CI platform
                    if ".github/workflows" in str(match):
                        ci_platforms["github_actions"] = (
                            ci_platforms.get("github_actions", 0) + 1
                        )
                    elif "gitlab-ci" in match.name:
                        ci_platforms["gitlab_ci"] = ci_platforms.get("gitlab_ci", 0) + 1
                    elif "travis" in match.name:
                        ci_platforms["travis_ci"] = ci_platforms.get("travis_ci", 0) + 1
                    elif "circleci" in str(match):
                        ci_platforms["circleci"] = ci_platforms.get("circleci", 0) + 1
                    elif "azure-pipelines" in match.name:
                        ci_platforms["azure_devops"] = (
                            ci_platforms.get("azure_devops", 0) + 1
                        )
                    elif "Jenkinsfile" in match.name:
                        ci_platforms["jenkins"] = ci_platforms.get("jenkins", 0) + 1
                    elif "drone" in match.name:
                        ci_platforms["drone"] = ci_platforms.get("drone", 0) + 1
                    elif "buildkite" in match.name:
                        ci_platforms["buildkite"] = ci_platforms.get("buildkite", 0) + 1

        return {
            "files": ci_files,
            "platforms": ci_platforms,
            "total_files": len(ci_files),
        }

    async def get_stats(self) -> dict[str, Any]:
        """Get analyzer statistics."""
        return {
            "analyzed_projects": len(self.analysis_cache),
            "cache_size": len(self.analysis_cache),
        }
