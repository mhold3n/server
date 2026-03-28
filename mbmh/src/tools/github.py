from .registry import register_tool
from .base import BaseTool

@register_tool("github")
class GithubTool(BaseTool):
    def execute(self, inputs):
        raise NotImplementedError("Disabled placeholder")
