"""Code indexing functionality for codebase datasets."""

import os
import hashlib
from typing import Any, Dict, List

import structlog
from git import Repo
from qdrant_client import QdrantClient
from tree_sitter import Language, Parser

from .embeddings import CodeEmbedder

logger = structlog.get_logger()


class CodeIndexer:
    """Indexes code repositories for search and retrieval."""

    def __init__(
        self,
        qdrant_client: QdrantClient,
        embedder: CodeEmbedder,
        collection_name: str = "code_resources",
    ):
        """Initialize code indexer.

        Args:
            qdrant_client: Qdrant client instance
            embedder: Code embedder instance
            collection_name: Qdrant collection name
        """
        self.qdrant_client = qdrant_client
        self.embedder = embedder
        self.collection_name = collection_name

        # Initialize tree-sitter parsers
        self.parsers = self._initialize_parsers()

    def _initialize_parsers(self) -> Dict[str, Parser]:
        """Initialize tree-sitter parsers for different languages.

        Returns:
            Dictionary of language parsers
        """
        parsers = {}

        # Language mappings
        language_mappings = {
            "python": "tree_sitter_python",
            "javascript": "tree_sitter_javascript",
            "typescript": "tree_sitter_typescript",
            "rust": "tree_sitter_rust",
            "go": "tree_sitter_go",
            "java": "tree_sitter_java",
            "cpp": "tree_sitter_cpp",
        }

        for lang, module_name in language_mappings.items():
            try:
                # Import the language module
                language_module = __import__(module_name)
                language = Language(language_module.language())

                parser = Parser()
                parser.set_language(language)

                parsers[lang] = parser
                logger.info("Initialized parser", language=lang)

            except ImportError:
                logger.warning(
                    "Failed to import parser", language=lang, module=module_name
                )

        return parsers

    async def initialize_collection(self) -> None:
        """Initialize Qdrant collection for code resources."""
        try:
            # Check if collection exists
            collections = self.qdrant_client.get_collections()
            collection_names = [c.name for c in collections.collections]

            if self.collection_name not in collection_names:
                # Create collection
                self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config={
                        "size": self.embedder.embedding_dim,
                        "distance": "Cosine",
                    },
                )
                logger.info(
                    "Created Qdrant collection", collection=self.collection_name
                )
            else:
                logger.info(
                    "Qdrant collection already exists", collection=self.collection_name
                )

        except Exception as e:
            logger.error("Failed to initialize collection", error=str(e))
            raise

    async def index_repository(
        self,
        repository_path: str,
        branch: str = "main",
    ) -> Dict[str, Any]:
        """Index a code repository.

        Args:
            repository_path: Path to repository
            branch: Branch to index

        Returns:
            Indexing results
        """
        try:
            # Open repository
            repo = Repo(repository_path)

            # Checkout branch
            if branch != repo.active_branch.name:
                repo.git.checkout(branch)

            # Get commit SHA
            commit_sha = repo.head.commit.hexsha

            # Index files
            files_indexed = 0
            functions_indexed = 0
            classes_indexed = 0

            for root, dirs, files in os.walk(repository_path):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith(".")]

                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, repository_path)

                    # Skip hidden files and non-code files
                    if file.startswith(".") or not self._is_code_file(file):
                        continue

                    try:
                        # Index file
                        file_results = await self._index_file(
                            file_path=file_path,
                            relative_path=relative_path,
                            repository_path=repository_path,
                            commit_sha=commit_sha,
                            branch=branch,
                        )

                        files_indexed += 1
                        functions_indexed += file_results["functions"]
                        classes_indexed += file_results["classes"]

                    except Exception as e:
                        logger.warning(
                            "Failed to index file",
                            file_path=relative_path,
                            error=str(e),
                        )

            results = {
                "repository_path": repository_path,
                "branch": branch,
                "commit_sha": commit_sha,
                "files_indexed": files_indexed,
                "functions_indexed": functions_indexed,
                "classes_indexed": classes_indexed,
            }

            logger.info("Repository indexing completed", **results)
            return results

        except Exception as e:
            logger.error(
                "Repository indexing failed",
                repository_path=repository_path,
                error=str(e),
            )
            raise

    def _is_code_file(self, filename: str) -> bool:
        """Check if file is a code file.

        Args:
            filename: Filename to check

        Returns:
            True if file is a code file
        """
        code_extensions = {
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".rs",
            ".go",
            ".java",
            ".cpp",
            ".c",
            ".h",
            ".hpp",
            ".cs",
            ".php",
            ".rb",
            ".swift",
            ".kt",
            ".scala",
            ".clj",
            ".hs",
            ".ml",
            ".fs",
        }

        _, ext = os.path.splitext(filename)
        return ext.lower() in code_extensions

    async def _index_file(
        self,
        file_path: str,
        relative_path: str,
        repository_path: str,
        commit_sha: str,
        branch: str,
    ) -> Dict[str, int]:
        """Index a single file.

        Args:
            file_path: Absolute file path
            relative_path: Relative file path
            repository_path: Repository root path
            commit_sha: Commit SHA
            branch: Branch name

        Returns:
            Indexing results for the file
        """
        try:
            # Read file content
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Determine language
            language = self._detect_language(file_path)

            # Parse file
            parsed_elements = self._parse_file(content, language)

            # Index elements
            functions_indexed = 0
            classes_indexed = 0

            for element in parsed_elements:
                # Create resource ID
                resource_id = self._create_resource_id(
                    repository_path=repository_path,
                    relative_path=relative_path,
                    element_type=element["type"],
                    element_name=element["name"],
                    line_start=element["line_start"],
                )

                # Create metadata
                metadata = {
                    "file_path": relative_path,
                    "language": language,
                    "element_type": element["type"],
                    "element_name": element["name"],
                    "line_start": element["line_start"],
                    "line_end": element["line_end"],
                    "content_length": len(element["content"]),
                }

                # Create provenance
                provenance = {
                    "repository": repository_path,
                    "commit_sha": commit_sha,
                    "branch": branch,
                    "indexed_at": self._get_timestamp(),
                }

                # Generate embedding
                embedding = self.embedder.embed_text(element["content"])

                # Store in Qdrant
                self.qdrant_client.upsert(
                    collection_name=self.collection_name,
                    points=[
                        {
                            "id": resource_id,
                            "vector": embedding,
                            "payload": {
                                "content": element["content"],
                                "metadata": metadata,
                                "provenance": provenance,
                            },
                        }
                    ],
                )

                if element["type"] == "function":
                    functions_indexed += 1
                elif element["type"] == "class":
                    classes_indexed += 1

            return {
                "functions": functions_indexed,
                "classes": classes_indexed,
            }

        except Exception as e:
            logger.error("Failed to index file", file_path=relative_path, error=str(e))
            raise

    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file path.

        Args:
            file_path: File path

        Returns:
            Language name
        """
        _, ext = os.path.splitext(file_path)

        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".rs": "rust",
            ".go": "go",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "cpp",
            ".h": "cpp",
            ".hpp": "cpp",
        }

        return language_map.get(ext.lower(), "unknown")

    def _parse_file(self, content: str, language: str) -> List[Dict[str, Any]]:
        """Parse file content to extract functions and classes.

        Args:
            content: File content
            language: Programming language

        Returns:
            List of parsed elements
        """
        if language not in self.parsers:
            # Fallback to simple text parsing
            return self._parse_text_fallback(content)

        parser = self.parsers[language]
        tree = parser.parse(bytes(content, "utf8"))

        elements = []

        # Language-specific parsing
        if language == "python":
            elements = self._parse_python(tree, content)
        elif language in ["javascript", "typescript"]:
            elements = self._parse_javascript(tree, content)
        elif language == "rust":
            elements = self._parse_rust(tree, content)
        elif language == "go":
            elements = self._parse_go(tree, content)
        elif language == "java":
            elements = self._parse_java(tree, content)
        elif language == "cpp":
            elements = self._parse_cpp(tree, content)

        return elements

    def _parse_python(self, tree, content: str) -> List[Dict[str, Any]]:
        """Parse Python code."""
        elements = []
        lines = content.split("\n")

        # Simple regex-based parsing for Python
        import re

        # Find functions
        function_pattern = r"^def\s+(\w+)\s*\([^)]*\):"
        for i, line in enumerate(lines):
            match = re.match(function_pattern, line.strip())
            if match:
                function_name = match.group(1)
                # Find function end
                end_line = self._find_function_end(lines, i)

                function_content = "\n".join(lines[i:end_line])

                elements.append(
                    {
                        "type": "function",
                        "name": function_name,
                        "content": function_content,
                        "line_start": i + 1,
                        "line_end": end_line,
                    }
                )

        # Find classes
        class_pattern = r"^class\s+(\w+)"
        for i, line in enumerate(lines):
            match = re.match(class_pattern, line.strip())
            if match:
                class_name = match.group(1)
                # Find class end
                end_line = self._find_class_end(lines, i)

                class_content = "\n".join(lines[i:end_line])

                elements.append(
                    {
                        "type": "class",
                        "name": class_name,
                        "content": class_content,
                        "line_start": i + 1,
                        "line_end": end_line,
                    }
                )

        return elements

    def _parse_javascript(self, tree, content: str) -> List[Dict[str, Any]]:
        """Parse JavaScript/TypeScript code."""
        elements = []
        lines = content.split("\n")

        import re

        # Find functions
        function_patterns = [
            r"^function\s+(\w+)\s*\(",
            r"^const\s+(\w+)\s*=\s*\([^)]*\)\s*=>",
            r"^(\w+)\s*:\s*function\s*\(",
        ]

        for i, line in enumerate(lines):
            for pattern in function_patterns:
                match = re.search(pattern, line.strip())
                if match:
                    function_name = match.group(1)
                    end_line = self._find_function_end(lines, i)

                    function_content = "\n".join(lines[i:end_line])

                    elements.append(
                        {
                            "type": "function",
                            "name": function_name,
                            "content": function_content,
                            "line_start": i + 1,
                            "line_end": end_line,
                        }
                    )
                    break

        return elements

    def _parse_rust(self, tree, content: str) -> List[Dict[str, Any]]:
        """Parse Rust code."""
        elements = []
        lines = content.split("\n")

        import re

        # Find functions
        function_pattern = r"^fn\s+(\w+)\s*\("
        for i, line in enumerate(lines):
            match = re.match(function_pattern, line.strip())
            if match:
                function_name = match.group(1)
                end_line = self._find_function_end(lines, i)

                function_content = "\n".join(lines[i:end_line])

                elements.append(
                    {
                        "type": "function",
                        "name": function_name,
                        "content": function_content,
                        "line_start": i + 1,
                        "line_end": end_line,
                    }
                )

        return elements

    def _parse_go(self, tree, content: str) -> List[Dict[str, Any]]:
        """Parse Go code."""
        elements = []
        lines = content.split("\n")

        import re

        # Find functions
        function_pattern = r"^func\s+(\w+)\s*\("
        for i, line in enumerate(lines):
            match = re.match(function_pattern, line.strip())
            if match:
                function_name = match.group(1)
                end_line = self._find_function_end(lines, i)

                function_content = "\n".join(lines[i:end_line])

                elements.append(
                    {
                        "type": "function",
                        "name": function_name,
                        "content": function_content,
                        "line_start": i + 1,
                        "line_end": end_line,
                    }
                )

        return elements

    def _parse_java(self, tree, content: str) -> List[Dict[str, Any]]:
        """Parse Java code."""
        elements = []
        lines = content.split("\n")

        import re

        # Find methods
        method_pattern = (
            r"^\s*(?:public|private|protected)?\s*(?:static)?\s*\w+\s+(\w+)\s*\("
        )
        for i, line in enumerate(lines):
            match = re.search(method_pattern, line.strip())
            if match:
                method_name = match.group(1)
                end_line = self._find_function_end(lines, i)

                method_content = "\n".join(lines[i:end_line])

                elements.append(
                    {
                        "type": "function",
                        "name": method_name,
                        "content": method_content,
                        "line_start": i + 1,
                        "line_end": end_line,
                    }
                )

        # Find classes
        class_pattern = r"^class\s+(\w+)"
        for i, line in enumerate(lines):
            match = re.match(class_pattern, line.strip())
            if match:
                class_name = match.group(1)
                end_line = self._find_class_end(lines, i)

                class_content = "\n".join(lines[i:end_line])

                elements.append(
                    {
                        "type": "class",
                        "name": class_name,
                        "content": class_content,
                        "line_start": i + 1,
                        "line_end": end_line,
                    }
                )

        return elements

    def _parse_cpp(self, tree, content: str) -> List[Dict[str, Any]]:
        """Parse C++ code."""
        elements = []
        lines = content.split("\n")

        import re

        # Find functions
        function_pattern = r"^\w+\s+(\w+)\s*\("
        for i, line in enumerate(lines):
            match = re.search(function_pattern, line.strip())
            if match:
                function_name = match.group(1)
                end_line = self._find_function_end(lines, i)

                function_content = "\n".join(lines[i:end_line])

                elements.append(
                    {
                        "type": "function",
                        "name": function_name,
                        "content": function_content,
                        "line_start": i + 1,
                        "line_end": end_line,
                    }
                )

        return elements

    def _parse_text_fallback(self, content: str) -> List[Dict[str, Any]]:
        """Fallback text parsing for unsupported languages."""
        elements = []
        lines = content.split("\n")

        # Simple chunking by lines
        chunk_size = 50
        for i in range(0, len(lines), chunk_size):
            chunk_lines = lines[i : i + chunk_size]
            chunk_content = "\n".join(chunk_lines)

            elements.append(
                {
                    "type": "chunk",
                    "name": f"chunk_{i // chunk_size + 1}",
                    "content": chunk_content,
                    "line_start": i + 1,
                    "line_end": min(i + chunk_size, len(lines)),
                }
            )

        return elements

    def _find_function_end(self, lines: List[str], start_line: int) -> int:
        """Find the end of a function."""
        brace_count = 0
        in_function = False

        for i in range(start_line, len(lines)):
            line = lines[i].strip()

            if not in_function:
                if "{" in line:
                    in_function = True
                    brace_count = line.count("{") - line.count("}")
                continue

            brace_count += line.count("{") - line.count("}")

            if brace_count == 0 and in_function:
                return i + 1

        return len(lines)

    def _find_class_end(self, lines: List[str], start_line: int) -> int:
        """Find the end of a class."""
        return self._find_function_end(lines, start_line)

    def _create_resource_id(
        self,
        repository_path: str,
        relative_path: str,
        element_type: str,
        element_name: str,
        line_start: int,
    ) -> str:
        """Create unique resource ID.

        Args:
            repository_path: Repository path
            relative_path: Relative file path
            element_type: Element type (function, class, etc.)
            element_name: Element name
            line_start: Start line number

        Returns:
            Unique resource ID
        """
        id_string = f"{repository_path}:{relative_path}:{element_type}:{element_name}:{line_start}"
        return hashlib.sha256(id_string.encode()).hexdigest()

    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime

        return datetime.utcnow().isoformat()
