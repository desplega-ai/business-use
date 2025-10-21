"""Internal models for Business-Use SDK."""

from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel

NodeType = Literal["act", "assert", "generic", "trigger", "hook"]
ExprEngine = Literal["python", "js", "cel"]


class Expr(BaseModel):
    """Expression that can be executed on the backend."""

    engine: ExprEngine
    script: str


class NodeCondition(BaseModel):
    """Condition for node execution."""

    timeout_ms: int | None = None


class EventBatchItem(BaseModel):
    """Event item for batch submission to backend API."""

    flow: str
    id: str
    run_id: str
    type: NodeType
    data: dict[str, Any]
    ts: int  # Nanoseconds timestamp
    description: str | None = None
    dep_ids: list[str] | None = None
    filter: Expr | None = None
    validator: Expr | None = None
    conditions: list[NodeCondition] | None = None
    additional_meta: dict[str, Any] | None = None


class QueuedEvent(BaseModel):
    """Internal representation of an event before batching."""

    model_config = {"arbitrary_types_allowed": True}

    flow: str
    id: str
    run_id: str | Callable[[], str]
    type: NodeType
    data: dict[str, Any]
    description: str | None = None
    dep_ids: list[str] | Callable[[], list[str]] | None = None
    filter: bool | Callable[[], bool] | None = None
    validator: Callable[[dict[str, Any], dict[str, Any]], bool] | None = None
    conditions: list[NodeCondition] | Callable[[], list[NodeCondition]] | None = None
    additional_meta: dict[str, Any] | None = None
