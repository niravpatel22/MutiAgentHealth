"""Shared response models: error envelope and pagination."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorBody(BaseModel):
    code: str = Field(examples=["unauthorized"])
    message: str = Field(examples=["Invalid email or password"])
    details: Any = None
    request_id: str | None = Field(default=None, examples=["5f0c3c1e9b2f4a6d8e7f1a2b3c4d5e6f"])


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class Page[T](BaseModel):
    items: list[T]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class PageParams(BaseModel):
    model_config = ConfigDict(frozen=True)

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def error_responses(*codes: int) -> dict[int | str, dict[str, Any]]:
    """OpenAPI ``responses=`` helper documenting the error envelope for the given codes."""
    descriptions = {
        400: "Bad request",
        401: "Missing, invalid, or expired credentials",
        403: "Authenticated but not allowed",
        404: "Resource not found (or not visible to you)",
        409: "Conflict with existing state",
        413: "Payload too large",
        415: "Unsupported media type",
        422: "Validation error",
        429: "Rate limit exceeded",
    }
    return {c: {"model": ErrorEnvelope, "description": descriptions.get(c, "Error")} for c in codes}
