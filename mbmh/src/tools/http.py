from .registry import register_tool
from .base import BaseTool

@register_tool("http")
class HttpTool(BaseTool):
    def execute(self, inputs):
        pass
