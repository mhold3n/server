from .registry import register_tool
from .base import BaseTool

@register_tool("slack")
class SlackTool(BaseTool):
    def execute(self, inputs):
        raise NotImplementedError("Disabled placeholder")
