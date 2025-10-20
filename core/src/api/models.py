from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel

from src.models import (
    DefinitionCondition,
    Handler,
    HandlerInput,
)


class SuccessResponse(BaseModel):
    status: Literal["success"] = "success"
    message: str
    data: dict[str, Any] | None = None  # noqa
    code: int | None = 200
    timestamp: datetime = datetime.now(UTC)


class DefinitionBaseSchema(BaseModel):
    description: str | None = None

    conditions: list[DefinitionCondition] | None = None
    dep_ids: list[str] | None = None

    filter: str | None = None
    validator: str | None = None

    handler: Handler | None = None
    handler_input: HandlerInput | None = None

    additional_meta: dict[str, Any] | None = None


class DefinitionCreateSchema(DefinitionBaseSchema):
    name: str
    x_id: str

    type: Literal["generic", "trigger", "hook"]


class DefinitionUpdateSchema(DefinitionBaseSchema):
    name: str | None = None
    x_id: str | None = None

    type: Literal["generic", "trigger", "hook"] | None = None


class EvalInput(BaseModel):
    ev_id: str
    whole_graph: bool = False
