from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import JSON, Column
from sqlmodel import BIGINT, Field, Index, String

from src.db.async_db import Base

Status = Literal[
    "active",
    "deleted",
]

EvalStatus = Literal[
    "pending",
    "running",
    "passed",
    "failed",
    "skipped",
    "error",
    "cancelled",
    "timed_out",
    "flaky",
]


class AuditBase(Base):
    status: Status = Field(
        default="active",
        sa_type=String,
        index=True,
    )
    created_at: datetime
    updated_at: datetime | None = None
    deleted_at: datetime | None = None


class CoreEnum(str, Enum):
    def __str__(self) -> str:
        return str.__str__(self)


NodeType = Literal[
    "generic",
    "trigger",
    "act",
    "assert",
    "hook",
]

NodeSource = Literal[
    "code",
    "manual",
]

ActionType = Literal[
    "http_request",
    "test_run",
    "test_suite_run",
    "command",
]


class ActionInputParams(BaseModel):
    url: str | None = None
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"] | None = None
    headers: dict[str, str] | None = None
    body: str | None = None
    timeout_ms: int | None = None

    test_run_id: str | None = None
    test_suite_run_id: str | None = None

    command: str | None = None

    # Run ID extractor for trigger nodes
    # Python expression to extract run_id from trigger context (input + output)
    run_id_extractor: Expr | None = None


class ActionInput(BaseModel):
    input_schema: dict[str, Any] | None = None
    params: ActionInputParams | None = None


class Event(Base, table=True):
    id: str = Field(primary_key=True)

    run_id: str = Field(
        index=True,
        description="The run identifier associated with this event.",
    )

    type: NodeType = Field(
        default="generic",
        sa_column=Column(String, index=True),
    )

    flow: str = Field(
        ...,
        index=True,
    )

    node_id: str = Field(
        ...,
        index=True,
    )

    data: dict[str, Any] = Field(
        default={},
        sa_column=Column(JSON),
        description="Event data used in the Node expression filters and validators",
    )

    ts: int = Field(
        sa_type=BIGINT,
        description="Timestamp in nanoseconds",
    )

    __table_args__ = (Index("idx_event_flow_node_id", "flow", "node_id"),)


class NodeCondition(BaseModel):
    timeout_ms: int | None = Field(
        default=None,
    )


ExprEngine = Literal["python", "js", "cel"]


class Expr(BaseModel):
    engine: ExprEngine
    script: str


class Node(AuditBase, table=True):
    """
    Node is a Business logic node.

    The (id, flow) pair SHOULD be unique, i.e., a flow can have multiple nodes,
    but a node id can only belong to one flow.
    """

    id: str = Field(
        ...,
        index=True,
        description="The id of the node, e.g. 'refund_stripe_approved_webhook'.",
        primary_key=True,
    )

    flow: str = Field(
        ...,
        index=True,
        description="The flow identifier to which this node belongs, e.g. 'refund'.",
    )

    type: NodeType = Field(
        default="generic",
        sa_column=Column(String, index=True),
    )

    source: NodeSource = Field(
        default="manual",
        sa_column=Column(String, index=True),
        description="Defines 'who' is the owner of this node",
    )

    description: str | None = Field(
        default=None,
    )

    dep_ids: list[str] = Field(
        default=[],
        sa_column=Column(JSON),
        description="List of node IDs that this node depends on.",
    )

    handler: ActionType | None = Field(
        default=None,
        sa_column=Column(String),
    )

    handler_input: ActionInput | None = Field(
        default=None,
        sa_column=Column(JSON),
    )

    filter: Expr | None = Field(
        default=None,
        sa_column=Column(JSON),
        description="Expression used by the SDKs",
    )

    validator: Expr | None = Field(
        default=None,
        sa_column=Column(JSON),
        description="Optional expression that performs an assertion on the node's upstream data.",
    )

    conditions: list[NodeCondition] = Field(
        default=[],
        sa_column=Column(JSON),
    )

    additional_meta: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON),
    )

    __table_args__ = (Index("idx_node_id_flow", "id", "flow"),)

    def ensure(self) -> None:
        if not self.dep_ids:
            self.dep_ids = []

        if isinstance(self.filter, dict):
            self.filter = Expr.model_validate(self.filter)

        if isinstance(self.validator, dict):
            self.validator = Expr.model_validate(self.validator)

        if isinstance(self.handler_input, dict):
            self.handler_input = ActionInput.model_validate(self.handler_input)

        if isinstance(self.conditions, list):
            self.conditions = [
                NodeCondition.model_validate(cond) for cond in self.conditions
            ]


class BaseEvalItemOutput(BaseModel):
    node_id: str
    dep_node_ids: list[str]

    status: EvalStatus

    message: str | None = None
    error: str | None = None

    elapsed_ns: int

    ev_ids: list[str] = []
    upstream_ev_ids: list[str] = []


class BaseEvalOutput(BaseModel):
    status: EvalStatus = "pending"
    elapsed_ns: int = 0
    graph: dict[str, list[str]] = {}
    exec_info: list[BaseEvalItemOutput] = []
    ev_ids: list[str] = []


class EvalOutput(AuditBase, table=True):
    id: str = Field(
        primary_key=True,
    )

    flow: str = Field(
        ...,
        index=True,
    )

    run_id: str | None = Field(
        default=None,
        index=True,
        description="The run identifier associated with this evaluation output, if applicable.",
    )

    trigger_ev_id: str | None = Field(
        default=None,
        index=True,
        description="The event ID that triggered this evaluation, if applicable.",
    )

    output: BaseEvalOutput = Field(
        sa_column=Column(JSON),
    )

    def ensure(self) -> None:
        if isinstance(self.output, dict):
            self.output = BaseEvalOutput.model_validate(self.output)
