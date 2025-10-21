from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel

from src.models import (
    ActionInput,
    ActionType,
    Expr,
    NodeCondition,
    NodeType,
)


class SuccessResponse(BaseModel):
    status: Literal["success"] = "success"
    message: str
    data: dict[str, Any] | None = None  # noqa
    code: int | None = 200
    timestamp: datetime = datetime.now(UTC)


class EventBatchItem(BaseModel):
    flow: str
    id: str
    run_id: str
    type: NodeType
    data: dict[str, Any]
    ts: int


class NodeBaseSchema(BaseModel):
    description: str | None = None

    conditions: list[NodeCondition] | None = None
    dep_ids: list[str] | None = None

    filter: Expr | None = None
    validator: Expr | None = None

    handler: ActionType | None = None
    handler_input: ActionInput | None = None

    additional_meta: dict[str, Any] | None = None


class NodeCreateSchema(NodeBaseSchema):
    flow: str
    id: str

    # Sub-set of the type as assert and act
    # should only be defined in code-defined nodes
    type: Literal["generic", "trigger", "hook"]


class NodeUpdateSchema(NodeBaseSchema):
    flow: str | None = None

    type: Literal["generic", "trigger", "hook"] | None = None


class EvalInput(BaseModel):
    ev_id: str
    whole_graph: bool = False
