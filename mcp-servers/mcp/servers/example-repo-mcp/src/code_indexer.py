"""
Code Indexer for Per-Repo MCP Server
Indexes codebases for fast search and analysis.
"""

import logging
from pathlib import Path
from typing import Any

from tree_sitter import Language, Parser

logger = logging.getLogger(__name__)


class CodeIndexer:
    """Indexes codebases for search and analysis."""

    def __init__(self):
        self.index: dict[str, Any] = {}
        self.languages: dict[str, Language] = {}
        self.parsers: dict[str, Parser] = {}
        self._load_language_parsers()

    def _load_language_parsers(self):
        """Load tree-sitter language parsers."""
        try:
            # Load Python parser
            self.languages["python"] = Language("tree_sitter_python", "python")
            self.parsers["python"] = Parser(self.languages["python"])

            # Load JavaScript parser
            self.languages["javascript"] = Language(
                "tree_sitter_javascript", "javascript"
            )
            self.parsers["javascript"] = Parser(self.languages["javascript"])

            # Load TypeScript parser
            self.languages["typescript"] = Language(
                "tree_sitter_typescript", "typescript"
            )
            self.parsers["typescript"] = Parser(self.languages["typescript"])

            logger.info("Loaded tree-sitter language parsers")

        except Exception as e:
            logger.warning(f"Failed to load some language parsers: {e}")

    async def index_codebase(
        self, path: Path, languages: list[str] = None, include_tests: bool = True
    ) -> dict[str, Any]:
        """Index a codebase for search and analysis."""
        if languages is None:
            languages = ["python", "javascript", "typescript"]

        logger.info(f"Indexing codebase at {path}")

        indexed_files = 0
        indexed_languages = set()
        total_size = 0

        # Walk through the codebase
        for file_path in self._get_code_files(path, languages, include_tests):
            try:
                # Read file content
                content = file_path.read_text(encoding="utf-8")
                file_size = len(content)
                total_size += file_size

                # Determine language
                language = self._detect_language(file_path)
                if language not in indexed_languages:
                    indexed_languages.add(language)

                # Parse and index the file
                await self._index_file(file_path, content, language)
                indexed_files += 1

                if indexed_files % 100 == 0:
                    logger.info(f"Indexed {indexed_files} files...")

            except Exception as e:
                logger.warning(f"Failed to index {file_path}: {e}")
                continue

        logger.info(
            f"Indexed {indexed_files} files in {len(indexed_languages)} languages"
        )

        return {
            "files_count": indexed_files,
            "languages": list(indexed_languages),
            "index_size": total_size,
        }

    def _get_code_files(
        self, path: Path, languages: list[str], include_tests: bool
    ) -> list[Path]:
        """Get list of code files to index."""
        extensions = {
            "python": [".py"],
            "javascript": [".js", ".jsx"],
            "typescript": [".ts", ".tsx"],
        }

        all_extensions = []
        for lang in languages:
            all_extensions.extend(extensions.get(lang, []))

        files = []
        for ext in all_extensions:
            for file_path in path.rglob(f"*{ext}"):
                # Skip hidden files and directories
                if any(part.startswith(".") for part in file_path.parts):
                    continue

                # Skip test files if not including tests
                if not include_tests and self._is_test_file(file_path):
                    continue

                # Skip common non-source directories
                if any(
                    part in ["node_modules", "__pycache__", ".git", "venv", "env"]
                    for part in file_path.parts
                ):
                    continue

                files.append(file_path)

        return files

    def _is_test_file(self, file_path: Path) -> bool:
        """Check if a file is a test file."""
        name = file_path.name.lower()
        return (
            name.startswith("test_")
            or name.endswith("_test.py")
            or name.endswith(".test.js")
            or name.endswith(".test.ts")
            or "test" in file_path.parts
        )

    def _detect_language(self, file_path: Path) -> str:
        """Detect the programming language of a file."""
        suffix = file_path.suffix.lower()

        if suffix in [".py"]:
            return "python"
        elif suffix in [".js", ".jsx"]:
            return "javascript"
        elif suffix in [".ts", ".tsx"]:
            return "typescript"
        else:
            return "unknown"

    async def _index_file(self, file_path: Path, content: str, language: str):
        """Index a single file."""
        relative_path = str(file_path.relative_to(file_path.anchor))

        # Parse the file if we have a parser for the language
        ast_data = None
        if language in self.parsers:
            try:
                ast_data = self._parse_file(content, language)
            except Exception as e:
                logger.warning(f"Failed to parse {file_path}: {e}")

        # Store in index
        self.index[relative_path] = {
            "path": relative_path,
            "language": language,
            "content": content,
            "size": len(content),
            "ast": ast_data,
            "functions": (
                self._extract_functions(ast_data, language) if ast_data else []
            ),
            "classes": self._extract_classes(ast_data, language) if ast_data else [],
            "imports": self._extract_imports(ast_data, language) if ast_data else [],
        }

    def _parse_file(self, content: str, language: str) -> dict[str, Any] | None:
        """Parse a file using tree-sitter."""
        if language not in self.parsers:
            return None

        parser = self.parsers[language]
        tree = parser.parse(bytes(content, "utf8"))

        return self._tree_to_dict(tree.root_node)

    def _tree_to_dict(self, node) -> dict[str, Any]:
        """Convert tree-sitter node to dictionary."""
        return {
            "type": node.type,
            "text": node.text.decode("utf8") if node.text else None,
            "start_point": node.start_point,
            "end_point": node.end_point,
            "children": [self._tree_to_dict(child) for child in node.children],
        }

    def _extract_functions(
        self, ast_data: dict[str, Any] | None, language: str
    ) -> list[dict[str, Any]]:
        """Extract function definitions from AST."""
        if not ast_data:
            return []

        functions = []

        def traverse(node):
            if node["type"] in ["function_definition", "method_definition"]:
                functions.append(
                    {
                        "name": self._get_function_name(node),
                        "type": node["type"],
                        "start_line": node["start_point"][0] + 1,
                        "end_line": node["end_point"][0] + 1,
                    }
                )

            for child in node.get("children", []):
                traverse(child)

        traverse(ast_data)
        return functions

    def _extract_classes(
        self, ast_data: dict[str, Any] | None, language: str
    ) -> list[dict[str, Any]]:
        """Extract class definitions from AST."""
        if not ast_data:
            return []

        classes = []

        def traverse(node):
            if node["type"] in ["class_definition", "class_declaration"]:
                classes.append(
                    {
                        "name": self._get_class_name(node),
                        "type": node["type"],
                        "start_line": node["start_point"][0] + 1,
                        "end_line": node["end_point"][0] + 1,
                    }
                )

            for child in node.get("children", []):
                traverse(child)

        traverse(ast_data)
        return classes

    def _extract_imports(
        self, ast_data: dict[str, Any] | None, language: str
    ) -> list[dict[str, Any]]:
        """Extract import statements from AST."""
        if not ast_data:
            return []

        imports = []

        def traverse(node):
            if node["type"] in [
                "import_statement",
                "import_from_statement",
                "import_declaration",
            ]:
                imports.append(
                    {
                        "type": node["type"],
                        "text": node["text"],
                        "line": node["start_point"][0] + 1,
                    }
                )

            for child in node.get("children", []):
                traverse(child)

        traverse(ast_data)
        return imports

    def _get_function_name(self, node: dict[str, Any]) -> str:
        """Extract function name from AST node."""
        for child in node.get("children", []):
            if child["type"] in ["identifier", "function_name"]:
                return child["text"]
        return "unknown"

    def _get_class_name(self, node: dict[str, Any]) -> str:
        """Extract class name from AST node."""
        for child in node.get("children", []):
            if child["type"] in ["identifier", "class_name"]:
                return child["text"]
        return "unknown"

    async def search(
        self, query: str, file_types: list[str] | None = None, max_results: int = 10
    ) -> list[dict[str, Any]]:
        """Search the indexed codebase."""
        results = []
        query_lower = query.lower()

        for file_path, file_data in self.index.items():
            # Filter by file types if specified
            if file_types and file_data["language"] not in file_types:
                continue

            # Search in content
            content = file_data["content"].lower()
            if query_lower in content:
                # Find line numbers where query appears
                lines = content.split("\n")
                matching_lines = []

                for i, line in enumerate(lines):
                    if query_lower in line:
                        matching_lines.append(
                            {"line_number": i + 1, "content": line.strip()}
                        )

                if matching_lines:
                    results.append(
                        {
                            "file": file_path,
                            "language": file_data["language"],
                            "matches": matching_lines[:5],  # Limit matches per file
                            "score": len(matching_lines),
                        }
                    )

            # Search in function names
            for func in file_data.get("functions", []):
                if query_lower in func["name"].lower():
                    results.append(
                        {
                            "file": file_path,
                            "language": file_data["language"],
                            "type": "function",
                            "name": func["name"],
                            "line": func["start_line"],
                            "score": 1,
                        }
                    )

            # Search in class names
            for cls in file_data.get("classes", []):
                if query_lower in cls["name"].lower():
                    results.append(
                        {
                            "file": file_path,
                            "language": file_data["language"],
                            "type": "class",
                            "name": cls["name"],
                            "line": cls["start_line"],
                            "score": 1,
                        }
                    )

        # Sort by score and limit results
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:max_results]

    async def get_stats(self) -> dict[str, Any]:
        """Get indexer statistics."""
        total_files = len(self.index)
        total_size = sum(file_data["size"] for file_data in self.index.values())

        languages = {}
        for file_data in self.index.values():
            lang = file_data["language"]
            languages[lang] = languages.get(lang, 0) + 1

        return {
            "total_files": total_files,
            "total_size": total_size,
            "languages": languages,
            "indexed_functions": sum(
                len(file_data.get("functions", [])) for file_data in self.index.values()
            ),
            "indexed_classes": sum(
                len(file_data.get("classes", [])) for file_data in self.index.values()
            ),
        }
