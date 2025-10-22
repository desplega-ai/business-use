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
    description: str | None = None

    run_id: str

    type: NodeType
    data: dict[str, Any]

    filter: Expr | None = None
    validator: Expr | None = None
    dep_ids: list[str] | None = None

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


class NodeYAMLCreateSchema(NodeBaseSchema):
    flow: str
    id: str
    type: NodeType


class NodeUpdateSchema(NodeBaseSchema):
    flow: str | None = None

    type: Literal["generic", "trigger", "hook"] | None = None


class EvalInput(BaseModel):
    """Evaluation input.

    Args:
        run_id: Run identifier
        flow: Flow identifier
        start_node_id: Optional node to start from (for subgraph eval)
    """

    # Required fields
    run_id: str
    flow: str
    start_node_id: str | None = None
