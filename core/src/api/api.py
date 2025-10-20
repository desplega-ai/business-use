import logging
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import desc
from sqlmodel import select

from src.api.middlewares import ensure_api_key
from src.api.models import (
    DefinitionCreateSchema,
    DefinitionUpdateSchema,
    EvalInput,
    SuccessResponse,
)
from src.db.transactional import transactional
from src.models import (
    Definition,
    EvalOutput,
    Event,
)
from src.utils import now

router = APIRouter(
    prefix="/v1",
    tags=[],
)


@router.get("/health")
async def health():
    return SuccessResponse(message="API is healthy")


@router.get("/check")
async def check(_: Annotated[None, Depends(ensure_api_key)]):
    return SuccessResponse(
        message="API key is valid",
    )


@router.get("/definitions")
async def get_definitions(_: Annotated[None, Depends(ensure_api_key)]):
    async with transactional() as s:
        defs = await s.execute(
            select(Definition).where(
                Definition.deleted_at.is_(None),  # type: ignore
            )
        )

        defs = defs.scalars().all()

    return defs


@router.get("/outputs")
async def get_outputs(
    _: Annotated[None, Depends(ensure_api_key)],
    name: Annotated[list[str] | None, Query()] = None,
    ev_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    async with transactional() as s:
        _s = select(EvalOutput)

        if name:
            _s = _s.where(EvalOutput.name.in_(name))  # type: ignore

        if ev_id:
            _s = _s.where(EvalOutput.trigger_ev_id == ev_id)

        _s = (
            _s.offset(offset)
            .limit(limit)
            .order_by(
                desc(EvalOutput.created_at)  # type: ignore
            )
        )

        outs = await s.execute(_s)
        outs = outs.scalars().all()

    return outs


@router.get("/events")
async def get_events(
    _: Annotated[None, Depends(ensure_api_key)],
    name: str | None = None,
    x_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    async with transactional() as s:
        _s = select(Event)

        if name:
            _s = _s.where(Event.name == name)

        if x_id:
            _s = _s.where(Event.x_id == x_id)

        _s = (
            _s.offset(offset)
            .limit(limit)
            .order_by(
                desc(Event.ts)  # type: ignore
            )
        )

        evs = await s.execute(_s)

        evs = evs.scalars().all()

    return evs


@router.post("/evaluate")
async def perform_eval(
    _: Annotated[None, Depends(ensure_api_key)],
    body: EvalInput,
):
    raise NotImplementedError("Evaluation endpoint not implemented yet")


@router.post("/definitions")
async def create_definition(
    _: Annotated[None, Depends(ensure_api_key)],
    body: DefinitionCreateSchema,
):
    async with transactional() as s:
        # Check for existing definition with same name and x_id
        existing_md = await s.execute(
            select(Definition).where(
                Definition.name == body.name,
                Definition.x_id == body.x_id,
            )
        )

        existing_md = existing_md.scalars().first()

        if existing_md and existing_md.deleted_at is None:
            raise HTTPException(
                status_code=400,
                detail="Definition with the same name and x_id already exists",
            )

        md = Definition(
            name=body.name,
            id=str(uuid4()),
            x_id=body.x_id,
            type=body.type,
            created_at=now(),
            status="active",
            description=body.description,
            conditions=body.conditions or [],
            dep_ids=body.dep_ids or [],
            handler=body.handler,
            handler_input=body.handler_input,
            additional_meta=body.additional_meta,
            source="manual",
        )

        if existing_md:
            md.created_at = existing_md.created_at
            md.deleted_at = None
            md.updated_at = now()
            md.id = existing_md.id

            await s.merge(md)

        else:
            s.add(md)

    return md


@router.put("/definitions/{definition_id}")
async def update_definition(
    definition_id: str,
    _: Annotated[None, Depends(ensure_api_key)],
    body: DefinitionUpdateSchema,
):
    async with transactional() as s:
        md = await s.get(Definition, definition_id)

        if not md:
            raise HTTPException(status_code=404, detail="Definition not found")

        if md.deleted_at is not None:
            md.deleted_at = None

        if md.source == "code":
            raise HTTPException(
                status_code=400,
                detail="Cannot update code-defined def",
            )

        update_data = body.model_dump(exclude_unset=True, exclude={"upstream_changes"})

        for key, value in update_data.items():
            setattr(md, key, value)

        md.updated_at = now()
        await s.merge(md)

    return md


@router.delete("/definitions/{definition_id}")
async def delete_definition(
    definition_id: str,
    _: Annotated[None, Depends(ensure_api_key)],
):
    async with transactional() as s:
        md = await s.get(Definition, definition_id)

        if not md:
            raise HTTPException(status_code=404, detail="Definition not found")

        if md.source == "code":
            raise HTTPException(
                status_code=400,
                detail="Cannot delete code-defined def",
            )

        md.updated_at = now()
        md.deleted_at = now()

        await s.merge(md)

    return SuccessResponse(message="Definition deleted")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("Starting up FastAPI")

    yield

    logging.info("Shutting down FastAPI")


app = FastAPI(lifespan=lifespan)

origins = [
    "http://localhost:3007",
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router)
