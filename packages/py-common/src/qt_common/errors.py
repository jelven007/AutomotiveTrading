from typing import Any

from pydantic import BaseModel, Field


class ProblemDetail(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    code: str
    trace_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ServiceError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}

    def to_problem(self, trace_id: str | None = None) -> ProblemDetail:
        return ProblemDetail(
            type=f"https://errors.quant-trading.local/{self.code}",
            title=self.message,
            status=self.status_code,
            detail=self.message,
            code=self.code,
            trace_id=trace_id,
            details=self.details,
        )
