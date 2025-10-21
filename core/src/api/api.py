import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import desc
from sqlmodel import select

from src.api.middlewares import ensure_api_key
from src.api.models import (
    EvalInput,
    NodeCreateSchema,
    NodeUpdateSchema,
    SuccessResponse,
)
from src.db.transactional import transactional
from src.models import (
    EvalOutput,
    Event,
    Node,
)
from src.utils import now

router = APIRouter(
    prefix="/v1",
    tags=[],
)


@router.get("/check")
async def check(_: Annotated[None, Depends(ensure_api_key)]):
    return SuccessResponse(
        message="lgtm",
    )


@router.get("/nodes")
async def get_nodes(_: Annotated[None, Depends(ensure_api_key)]):
    async with transactional() as s:
        defs = await s.execute(
            select(Node).where(
                Node.deleted_at.is_(None),  # type: ignore
            )
        )

        defs = defs.scalars().all()

    return defs


@router.get("/eval-outputs")
async def get_eval_outputs(
    _: Annotated[None, Depends(ensure_api_key)],
    name: Annotated[list[str] | None, Query()] = None,
    ev_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    async with transactional() as s:
        _s = select(EvalOutput)

        if name:
            _s = _s.where(EvalOutput.flow.in_(name))  # type: ignore

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
    flow: str | None = None,
    node_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    async with transactional() as s:
        _s = select(Event)

        if flow:
            _s = _s.where(Event.flow == flow)

        if node_id:
            _s = _s.where(Event.node_id == node_id)

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


@router.post("/eval")
async def perform_eval(
    _: Annotated[None, Depends(ensure_api_key)],
    body: EvalInput,
):
    raise NotImplementedError("Evaluation endpoint not implemented yet")


@router.post("/node")
async def create_node(
    _: Annotated[None, Depends(ensure_api_key)],
    body: NodeCreateSchema,
):
    async with transactional() as s:
        existing_md = await s.get(Node, body.id)

        if existing_md and existing_md.flow == body.flow:
            raise HTTPException(
                status_code=400,
                detail="Node with the same name and id already exists",
            )

        md = Node(
            flow=body.flow,
            id=body.id,
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

            # Revive the node if it was deleted
            md.deleted_at = None
            md.updated_at = now()

            await s.merge(md)

        else:
            s.add(md)

    return md


@router.put("/node/{node_id}")
async def update_node(
    node_id: str,
    _: Annotated[None, Depends(ensure_api_key)],
    body: NodeUpdateSchema,
):
    async with transactional() as s:
        md = await s.get(Node, node_id)

        if not md:
            raise HTTPException(status_code=404, detail="Node not found")

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


@router.delete("/node/{node_id}")
async def delete_definition(
    node_id: str,
    _: Annotated[None, Depends(ensure_api_key)],
):
    async with transactional() as s:
        md = await s.get(Node, node_id)

        if not md:
            raise HTTPException(status_code=404, detail="Node not found")

        if md.source == "code":
            raise HTTPException(
                status_code=400,
                detail="Cannot delete code-defined def",
            )

        md.updated_at = now()
        md.deleted_at = now()

        await s.merge(md)

    return SuccessResponse(message="Node deleted")


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


@app.get("/health")
async def health():
    return SuccessResponse(message="API is healthy")
