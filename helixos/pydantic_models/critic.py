from typing import Literal

from pydantic import BaseModel


class CriticVerdict(BaseModel):
    status: Literal['pass', 'warn', 'halt']
    failure_mode: str | None = None
    recommendation: str | None = None
