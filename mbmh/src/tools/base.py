from pydantic import BaseModel
from typing import Dict, Any

class BaseTool(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    auth_requirements: list
    
    def execute(self, inputs: Dict[str, Any]) -> Any:
        raise NotImplementedError
