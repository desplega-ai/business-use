import logging
import time
import warnings
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, TypedDict
from uuid import uuid4

from bubus import EventBus
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import desc
from sqlmodel import select

from src import __version__
from src.api.middlewares import ensure_api_key
from src.api.models import (
    EvalInput,
    EventBatchItem,
    HealthResponse,
    NodeCreateSchema,
    NodeUpdateSchema,
    ReEvalResponse,
    RootResponse,
    ScanUploadPayload,
    ScanUploadResponse,
    SuccessResponse,
)
from src.db.transactional import transactional
from src.events.handlers import new_bus
from src.events.models import NewBatchEvent
from src.models import (
    BaseEvalOutput,
    EvalOutput,
    Event,
    Node,
)
from src.utils.time import now

# Suppress Pydantic serialization warnings for dict-stored JSON fields
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module="pydantic.main",
    message=".*Pydantic serializer warnings.*",
)

log = logging.getLogger(__name__)


class AppState(TypedDict):
    bus: EventBus


router = APIRouter(
    prefix="/v1",
    tags=[],
)


@router.get("/status", response_model=SuccessResponse)
async def status(_: Annotated[None, Depends(ensure_api_key)]):
    return SuccessResponse(
        message="ok",
    )


@router.get("/eval-outputs", response_model=list[EvalOutput])
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


@router.post("/events-batch", response_model=SuccessResponse)
async def persist_events_batch(
    _: Annotated[None, Depends(ensure_api_key)],
    request: Request,
    body: list[EventBatchItem],
):
    ids: list[str] = []

    # NOTE
    # This is not optimal for large batches, and it's intended to be
    # used locally for now.
    async with transactional() as s:
        nodes: list[Node] = []

        for item in body:
            ev = Event(
                id=str(uuid4()),
                flow=item.flow,
                node_id=item.id,
                run_id=item.run_id,
                type=item.type,
                data=item.data,
                ts=item.ts,
            )

            ids.append(ev.id)
            s.add(ev)

            nodes.append(
                Node(
                    id=item.id,
                    flow=item.flow,
                    type=item.type,
                    source="code",
                    description=item.description,
                    dep_ids=item.dep_ids or [],
                    validator=item.validator,
                    filter=item.filter,
                    conditions=[],
                    additional_meta=None,
                    created_at=now(),
                )
            )

        # Upsert nodes - but don't overwrite user-edited fields
        for node in nodes:
            existing_node = await s.get(Node, node.id)

            if existing_node:
                # SDK events upgrade both "code" and "scan" nodes.
                # "scan" nodes only have metadata (has_validator bool) — SDK
                # provides the real serialized validators, so it takes precedence.
                # Only "manual" (user-edited in UI) nodes are protected.
                if existing_node.source in ("code", "scan"):
                    existing_node.source = "code"
                    existing_node.type = node.type
                    existing_node.description = node.description
                    existing_node.dep_ids = node.dep_ids
                    existing_node.validator = node.validator
                    existing_node.filter = node.filter
                    existing_node.conditions = node.conditions
                    existing_node.additional_meta = node.additional_meta
                    existing_node.updated_at = now()
                    await s.merge(existing_node)
                # If source is "manual", don't update - user has edited in UI

            else:
                s.add(node)

    b: EventBus = request.state.bus

    # Notify new batch of events
    b.dispatch(NewBatchEvent(ev_ids=ids))

    return SuccessResponse(
        message="Ok",
    )


@router.get("/events", response_model=list[Event])
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


@router.post("/run-eval", response_model=BaseEvalOutput)
async def run_eval(
    _: Annotated[None, Depends(ensure_api_key)],
    body: EvalInput,
):
    """Run flow evaluation.

    The body must contain:
    - run_id: Run identifier
    - flow: Flow identifier
    - start_node_id: Optional node to start from (for subgraph eval)

    Results are automatically persisted to the database.
    """
    from src.eval import eval_flow_run

    result = await eval_flow_run(
        run_id=body.run_id,
        flow=body.flow,
        start_node_id=body.start_node_id,
    )

    # Persist evaluation result to database
    async with transactional() as session:
        eval_output = EvalOutput(
            id=str(uuid4()),
            flow=body.flow,
            run_id=body.run_id,
            trigger_ev_id=None,
            output=result,
            created_at=now(),
            status="active",
        )

        session.add(eval_output)
        await session.commit()

    return result


@router.post("/reeval-running-flows", response_model=ReEvalResponse)
async def reeval_running_flows(
    _: Annotated[None, Depends(ensure_api_key)],
    max_age_seconds: int = 86400,  # 24 hours default
):
    """Re-evaluate flows stuck in 'running' state.

    This endpoint should be called periodically by an external cron job (every 30s recommended).
    It re-evaluates recent EvalOutputs with status='running' to check if timeouts have expired.

    Args:
        max_age_seconds: Only check evaluations created within this time window (default: 24 hours)

    Returns:
        JSON with counts: total_running, updated, still_running, failed

    Example cron:
        * * * * * curl -X POST http://localhost:13370/v1/reeval-running-flows -H "X-Api-Key: KEY"
        * * * * * sleep 30 && curl -X POST http://localhost:13370/v1/reeval-running-flows -H "X-Api-Key: KEY"
    """
    from datetime import datetime, timedelta

    from src.eval import eval_flow_run

    cutoff_time = datetime.utcnow() - timedelta(seconds=max_age_seconds)

    async with transactional() as session:
        # Find recent EvalOutputs with running status
        stmt = (
            select(EvalOutput)
            .where(
                EvalOutput.output["status"].astext == "running",  # type: ignore
                EvalOutput.created_at >= cutoff_time,
            )
            .order_by(desc(EvalOutput.created_at))  # type: ignore
        )

        results = await session.execute(stmt)
        running_evals = results.scalars().all()

        log.info(f"Found {len(running_evals)} running evaluations to re-check")

        updated_count = 0
        still_running_count = 0
        failed_count = 0

        for eval_output in running_evals:
            try:
                # Re-evaluate
                new_result = await eval_flow_run(
                    run_id=eval_output.run_id,
                    flow=eval_output.flow,
                )

                # Update output and timestamp
                old_status = eval_output.output.status
                eval_output.output = new_result
                eval_output.updated_at = now()
                await session.merge(eval_output)

                # Track status changes
                if new_result.status != old_status:
                    log.info(
                        f"Status changed for {eval_output.flow}/{eval_output.run_id}: "
                        f"{old_status} → {new_result.status}"
                    )
                    updated_count += 1
                else:
                    still_running_count += 1

            except Exception as e:
                log.exception(
                    f"Failed to re-evaluate {eval_output.flow}/{eval_output.run_id}: {e}"
                )
                failed_count += 1
                continue

        await session.commit()

    return {
        "message": "Re-evaluation complete",
        "total_running": len(running_evals),
        "updated": updated_count,
        "still_running": still_running_count,
        "failed": failed_count,
    }


@router.get("/nodes", response_model=list[Node])
async def get_nodes(_: Annotated[None, Depends(ensure_api_key)]):
    async with transactional() as s:
        defs = await s.execute(
            select(Node).where(
                Node.deleted_at.is_(None),  # type: ignore
            )
        )

        defs = defs.scalars().all()

    return defs


@router.post("/nodes", response_model=Node)
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


@router.put("/nodes/{node_id}", response_model=Node)
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


@router.delete("/nodes/{node_id}", response_model=SuccessResponse)
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


@router.post("/nodes/scan", response_model=ScanUploadResponse)
async def upload_scan(
    _: Annotated[None, Depends(ensure_api_key)],
    body: ScanUploadPayload,
):
    """Batch upsert nodes from scanner output.

    Accepts the scanner CLI output and upserts nodes with source="scan".
    Nodes that existed with source="scan" but are no longer in the payload
    are soft-deleted.
    """
    created = 0
    updated = 0
    deleted = 0

    async with transactional() as s:
        # Collect all node IDs from the payload, grouped by flow
        payload_node_ids_by_flow: dict[str, set[str]] = {}

        for flow_name, scanned_nodes in body.flows.items():
            payload_node_ids_by_flow[flow_name] = set()

            for body_node in scanned_nodes:
                payload_node_ids_by_flow[flow_name].add(body_node.id)

                existing_node = await s.get(Node, body_node.id)

                if existing_node:
                    # Update existing node
                    existing_node.flow = body_node.flow
                    existing_node.type = body_node.type
                    existing_node.source = "scan"
                    existing_node.description = body_node.description
                    existing_node.dep_ids = body_node.dep_ids
                    existing_node.conditions = body_node.conditions
                    existing_node.updated_at = now()
                    existing_node.deleted_at = None
                    await s.merge(existing_node)
                    updated += 1
                else:
                    # Create new node
                    node = Node(
                        id=body_node.id,
                        flow=body_node.flow,
                        type=body_node.type,
                        source="scan",
                        description=body_node.description,
                        dep_ids=body_node.dep_ids,
                        conditions=body_node.conditions,
                        created_at=now(),
                        status="active",
                    )
                    s.add(node)
                    created += 1

        # Soft-delete stale scan nodes per flow
        for flow_name, payload_ids in payload_node_ids_by_flow.items():
            stmt = select(Node).where(
                Node.flow == flow_name,
                Node.source == "scan",
                Node.deleted_at.is_(None),  # type: ignore
            )
            result = await s.execute(stmt)
            existing_scan_nodes = result.scalars().all()

            for node in existing_scan_nodes:
                if node.id not in payload_ids:
                    node.deleted_at = now()
                    node.updated_at = now()
                    await s.merge(node)
                    deleted += 1

    return ScanUploadResponse(
        created=created,
        updated=updated,
        deleted=deleted,
        flows=list(body.flows.keys()),
    )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[AppState]:
    yield {
        "bus": new_bus(),
    }

    log.info("Ciaito!")


app = FastAPI(
    title="business-use",
    version=__version__,
    description="Business event flow tracking and validation",
    lifespan=lifespan,
)

origins = [
    "http://localhost:3007",
    "http://localhost:13370",
    "http://localhost:5174",
    "https://business-use.vercel.app",
    "https://business-use.desplega.ai",
    "https://business-use.com",
    "https://www.business-use.com",
    "https://ui.business-use.com",
    # TODO: Remove
    "*",
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


@app.get("/", response_model=RootResponse)
async def root():
    start = time.monotonic()
    return {
        "name": "business-use",
        "version": __version__,
        "status": "ok",
        "latency_ms": round((time.monotonic() - start) * 1000, 2),
        "health": "/health",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


@app.get("/health", response_model=HealthResponse)
async def health():
    return {"status": "ok", "version": __version__}
