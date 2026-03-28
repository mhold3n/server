from .registry import register_tool
from .base import BaseTool

@register_tool("email")
class EmailTool(BaseTool):
    def execute(self, inputs):
        raise NotImplementedError("Disabled placeholder")
