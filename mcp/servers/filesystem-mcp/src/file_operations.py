"""File operations for the filesystem MCP server."""

import fnmatch
import re
from pathlib import Path
from typing import Any, cast

import aiofiles
import structlog

logger = structlog.get_logger()


class FileOperations:
    """File system operations."""

    def __init__(self, base_path: str = "/workspace"):
        """Initialize file operations with base path."""
        self.base_path = Path(base_path).resolve()
        logger.info("Initialized file operations", base_path=str(self.base_path))

    def _resolve_path(self, path: str) -> Path:
        """Resolve a path relative to the base path."""
        resolved = (self.base_path / path).resolve()

        # Security check: ensure path is within base_path
        try:
            resolved.relative_to(self.base_path)
        except ValueError:
            raise ValueError(f"Path {path} is outside allowed directory") from None

        return resolved

    async def read_file(self, path: str, encoding: str = "utf-8") -> str:
        """Read the contents of a file."""
        try:
            file_path = self._resolve_path(path)

            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {path}")

            if not file_path.is_file():
                raise ValueError(f"Path is not a file: {path}")

            async with aiofiles.open(file_path, encoding=encoding) as f:
                content = await f.read()

            logger.info("Read file", path=path, size=len(content))
            return content

        except Exception as e:
            logger.error("Failed to read file", path=path, error=str(e))
            raise

    async def write_file(
        self, path: str, content: str, encoding: str = "utf-8"
    ) -> dict[str, Any]:
        """Write content to a file."""
        try:
            file_path = self._resolve_path(path)

            # Create parent directories if they don't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)

            async with aiofiles.open(file_path, "w", encoding=encoding) as f:
                await f.write(content)

            logger.info("Wrote file", path=path, size=len(content))
            return {
                "path": str(file_path),
                "size": len(content),
                "created": not file_path.exists() or file_path.stat().st_size == 0,
            }

        except Exception as e:
            logger.error("Failed to write file", path=path, error=str(e))
            raise

    async def list_directory(
        self, path: str, recursive: bool = False, include_hidden: bool = False
    ) -> dict[str, Any]:
        """List contents of a directory."""
        try:
            dir_path = self._resolve_path(path)

            if not dir_path.exists():
                raise FileNotFoundError(f"Directory not found: {path}")

            if not dir_path.is_dir():
                raise ValueError(f"Path is not a directory: {path}")

            items: list[dict[str, Any]] = []

            if recursive:
                for item_path in dir_path.rglob("*"):
                    if not include_hidden and item_path.name.startswith("."):
                        continue

                    relative_path = item_path.relative_to(dir_path)
                    items.append(
                        {
                            "name": item_path.name,
                            "path": str(relative_path),
                            "type": "directory" if item_path.is_dir() else "file",
                            "size": (
                                item_path.stat().st_size
                                if item_path.is_file()
                                else None
                            ),
                            "modified": item_path.stat().st_mtime,
                        }
                    )
            else:
                for item_path in dir_path.iterdir():
                    if not include_hidden and item_path.name.startswith("."):
                        continue

                    items.append(
                        {
                            "name": item_path.name,
                            "path": item_path.name,
                            "type": "directory" if item_path.is_dir() else "file",
                            "size": (
                                item_path.stat().st_size
                                if item_path.is_file()
                                else None
                            ),
                            "modified": item_path.stat().st_mtime,
                        }
                    )

            # Sort items: directories first, then files, both alphabetically
            items.sort(
                key=lambda x: (
                    cast(str, x["type"]) != "directory",
                    cast(str, x["name"]).lower(),
                )
            )

            logger.info(
                "Listed directory", path=path, count=len(items), recursive=recursive
            )
            return {
                "path": str(dir_path),
                "items": items,
                "count": len(items),
            }

        except Exception as e:
            logger.error("Failed to list directory", path=path, error=str(e))
            raise

    async def search_files(
        self, pattern: str, root_path: str = ".", include_hidden: bool = False
    ) -> dict[str, Any]:
        """Search for files matching a pattern."""
        try:
            search_path = self._resolve_path(root_path)

            if not search_path.exists():
                raise FileNotFoundError(f"Search path not found: {root_path}")

            if not search_path.is_dir():
                raise ValueError(f"Search path is not a directory: {root_path}")

            matches: list[dict[str, Any]] = []

            for file_path in search_path.rglob("*"):
                if not include_hidden and file_path.name.startswith("."):
                    continue

                if file_path.is_file() and fnmatch.fnmatch(file_path.name, pattern):
                    relative_path = file_path.relative_to(search_path)
                    matches.append(
                        {
                            "name": file_path.name,
                            "path": str(relative_path),
                            "size": file_path.stat().st_size,
                            "modified": file_path.stat().st_mtime,
                        }
                    )

            # Sort by path
            matches.sort(key=lambda x: cast(str, x["path"]))

            logger.info("Searched files", pattern=pattern, matches=len(matches))
            return {
                "pattern": pattern,
                "root_path": str(search_path),
                "matches": matches,
                "count": len(matches),
            }

        except Exception as e:
            logger.error("Failed to search files", pattern=pattern, error=str(e))
            raise

    async def search_content(
        self,
        query: str,
        root_path: str = ".",
        file_pattern: str | None = None,
        exclude_pattern: str | None = None,
        case_sensitive: bool = False,
    ) -> dict[str, Any]:
        """Search for content within files."""
        try:
            search_path = self._resolve_path(root_path)

            if not search_path.exists():
                raise FileNotFoundError(f"Search path not found: {root_path}")

            if not search_path.is_dir():
                raise ValueError(f"Search path is not a directory: {root_path}")

            # Compile regex
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                regex = re.compile(query, flags)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {e}") from e

            matches: list[dict[str, Any]] = []

            for file_path in search_path.rglob("*"):
                if not file_path.is_file():
                    continue

                # Skip hidden files
                if file_path.name.startswith("."):
                    continue

                # Apply file pattern filter
                if file_pattern and not fnmatch.fnmatch(file_path.name, file_pattern):
                    continue

                # Apply exclude pattern filter
                if exclude_pattern and fnmatch.fnmatch(file_path.name, exclude_pattern):
                    continue

                try:
                    # Read file content
                    async with aiofiles.open(
                        file_path, encoding="utf-8", errors="ignore"
                    ) as f:
                        content = await f.read()

                    # Search for matches
                    file_matches = []
                    for match in regex.finditer(content):
                        # Get context around the match
                        start = max(0, match.start() - 50)
                        end = min(len(content), match.end() + 50)
                        context = content[start:end]

                        # Find line number
                        line_num = content[: match.start()].count("\n") + 1

                        file_matches.append(
                            {
                                "line": line_num,
                                "column": match.start()
                                - content.rfind("\n", 0, match.start())
                                - 1,
                                "match": match.group(),
                                "context": context.strip(),
                            }
                        )

                    if file_matches:
                        relative_path = file_path.relative_to(search_path)
                        matches.append(
                            {
                                "file": str(relative_path),
                                "matches": file_matches,
                                "count": len(file_matches),
                            }
                        )

                except Exception as e:
                    logger.warning(
                        "Failed to search in file", file=str(file_path), error=str(e)
                    )
                    continue

            # Sort by file path
            matches.sort(key=lambda x: cast(str, x["file"]))

            total_matches = sum(cast(int, match["count"]) for match in matches)

            logger.info(
                "Searched content",
                query=query,
                files_searched=len(list(search_path.rglob("*"))),
                files_matched=len(matches),
                total_matches=total_matches,
            )

            return {
                "query": query,
                "root_path": str(search_path),
                "file_pattern": file_pattern,
                "exclude_pattern": exclude_pattern,
                "case_sensitive": case_sensitive,
                "matches": matches,
                "files_matched": len(matches),
                "total_matches": total_matches,
            }

        except Exception as e:
            logger.error("Failed to search content", query=query, error=str(e))
            raise
