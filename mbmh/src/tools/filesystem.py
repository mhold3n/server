from .registry import register_tool
from .base import BaseTool

@register_tool("filesystem")
class FilesystemTool(BaseTool):
    # Minimal skeleton
    def execute(self, inputs):
        pass
