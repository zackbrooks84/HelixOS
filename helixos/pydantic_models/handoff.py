from typing import Any

from pydantic import BaseModel


class HandoffPayload(BaseModel):
    target_agent: str
    task_summary: str
    context: dict[str, Any]
    artifacts: list[str] = []
    priority: int = 1
