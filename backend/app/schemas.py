from pydantic import BaseModel
from typing import Any

class InitRequest(BaseModel):
    tools_list: list[dict[str, Any]]

