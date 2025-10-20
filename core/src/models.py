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

RunStatus = Literal[
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


DefinitionType = Literal[
    "generic",
    "trigger",
    "act",
    "assert",
    "hook",
]

DefinitionSource = Literal[
    "code",
    "manual",
]

Handler = Literal[
    "http_request",
    "test_run",
    "test_suite_run",
]


class HandlerInputParams(BaseModel):
    url: str | None = None
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"] | None = None
    headers: dict[str, str] | None = None
    body: str | None = None
    timeout_ms: int | None = None

    test_run_id: str | None = None
    test_suite_run_id: str | None = None


class HandlerInput(BaseModel):
    input_schema: dict[str, Any] | None = None
    params: HandlerInputParams | None = None


class Event(Base, table=True):
    id: str = Field(primary_key=True)

    workflow_run_id: str | None = Field(
        default=None,
        index=True,
    )

    type: DefinitionType = Field(
        default="generic",
        sa_column=Column(String, index=True),
    )

    name: str = Field(
        ...,
        index=True,
    )

    x_id: str = Field(
        ...,
        index=True,
    )

    data: dict[str, Any] = Field(
        default={},
        sa_column=Column(JSON),
    )

    ts: int = Field(
        sa_type=BIGINT,
    )

    __table_args__ = (Index("idx_event_name_xid", "name", "x_id"),)


class DefinitionCondition(BaseModel):
    timeout_ms: int | None = Field(
        default=None,
    )


class Definition(AuditBase, table=True):
    id: str = Field(primary_key=True)

    type: DefinitionType = Field(
        default="generic",
        sa_column=Column(String, index=True),
    )

    source: DefinitionSource = Field(
        default="manual",
        sa_column=Column(String, index=True),
    )

    handler: Handler | None = Field(
        default=None,
        sa_column=Column(String),
    )

    handler_input: HandlerInput | None = Field(
        default=None,
        sa_column=Column(JSON),
    )

    name: str = Field(
        ...,
        index=True,
    )

    description: str | None = Field(
        default=None,
    )

    x_id: str = Field(
        ...,
        index=True,
    )

    dep_ids: list[str] = Field(
        default=[],
        sa_column=Column(JSON),
    )

    filter: str | None = Field(
        default=None,
    )

    validator: str | None = Field(
        default=None,
    )

    conditions: list[DefinitionCondition] = Field(
        default=[],
        sa_column=Column(JSON),
    )

    additional_meta: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON),
    )

    __table_args__ = (Index("idx_definition_name_xid", "name", "x_id"),)

    def ensure(self) -> None:
        if not self.dep_ids:
            self.dep_ids = []

        if isinstance(self.conditions, list):
            self.conditions = [
                DefinitionCondition.model_validate(cond) for cond in self.conditions
            ]


class BaseEvalItemOutput(BaseModel):
    x_id: str
    dep_x_ids: list[str]

    status: RunStatus

    message: str | None = None
    error: str | None = None

    elapsed_ns: int

    ev_ids: list[str] = []
    upstream_ev_ids: list[str] = []


class BaseEvalOutput(BaseModel):
    status: RunStatus = "pending"
    elapsed_ns: int = 0
    graph: dict[str, list[str]] = {}
    exec_info: list[BaseEvalItemOutput] = []
    ev_ids: list[str] = []


class EvalOutput(AuditBase, table=True):
    id: str = Field(primary_key=True)

    name: str = Field(
        ...,
        index=True,
    )

    trigger_ev_id: str = Field(
        ...,
        index=True,
    )

    output: BaseEvalOutput = Field(
        sa_column=Column(JSON),
        description="The output of the magic evaluation, including status, elapsed time, execution info, and event IDs.",
    )

    def ensure(self) -> None:
        if isinstance(self.output, dict):
            self.output = BaseEvalOutput.model_validate(self.output)
