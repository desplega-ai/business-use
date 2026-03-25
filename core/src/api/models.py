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


class RootResponse(BaseModel):
    name: str
    version: str
    status: str
    latency_ms: float
    health: str
    docs: str
    openapi: str


class HealthResponse(BaseModel):
    status: str
    version: str


class SuccessResponse(BaseModel):
    status: Literal["success"] = "success"
    message: str
    data: dict[str, Any] | None = None  # noqa
    code: int | None = 200
    timestamp: datetime = datetime.now(UTC)


class ReEvalResponse(BaseModel):
    message: str
    total_running: int
    updated: int
    still_running: int
    failed: int


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


# --- Scanner models ---


class ScannedNode(BaseModel):
    """A node extracted by the scanner."""

    id: str
    flow: str
    type: Literal["act", "assert"]
    dep_ids: list[str] = []
    description: str | None = None
    conditions: list[NodeCondition] = []
    has_filter: bool = False
    has_validator: bool = False
    source_file: str | None = None
    source_line: int | None = None
    source_column: int | None = None


class ScanUploadPayload(BaseModel):
    """Payload from the scanner CLI."""

    version: str = "1.0"
    scanned_at: str
    files_scanned: int
    flows: dict[str, list[ScannedNode]]


class ScanUploadResponse(BaseModel):
    """Response from the scan upload endpoint."""

    created: int
    updated: int
    deleted: int
    flows: list[str]
