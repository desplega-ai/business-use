"""Tests for POST /v1/nodes/scan — scanner batch upsert endpoint.

Includes both schema validation tests and integration tests that
hit the actual endpoint, verify DB state, and test auth enforcement.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select

from src.api.api import app
from src.api.middlewares import ensure_api_key
from src.api.models import ScannedNode, ScanUploadPayload, ScanUploadResponse
from src.models import Node

# ---------------------------------------------------------------------------
# Schema validation tests (unit-level)
# ---------------------------------------------------------------------------


def test_scanned_node_minimal():
    node = ScannedNode(id="checkout_start", flow="checkout", type="act")
    assert node.id == "checkout_start"
    assert node.flow == "checkout"
    assert node.type == "act"
    assert node.dep_ids == []
    assert node.description is None
    assert node.conditions == []
    assert node.has_filter is False
    assert node.has_validator is False
    assert node.source_file is None
    assert node.source_line is None
    assert node.source_column is None


def test_scanned_node_full():
    node = ScannedNode(
        id="payment_processed",
        flow="checkout",
        type="assert",
        dep_ids=["checkout_start"],
        description="Payment was processed",
        conditions=[{"timeout_ms": 5000}],
        has_filter=True,
        has_validator=True,
        source_file="src/checkout.ts",
        source_line=42,
        source_column=10,
    )
    assert node.type == "assert"
    assert node.dep_ids == ["checkout_start"]
    assert node.has_filter is True
    assert node.has_validator is True
    assert node.source_file == "src/checkout.ts"
    assert node.source_line == 42
    assert node.source_column == 10
    assert len(node.conditions) == 1


def test_scanned_node_rejects_invalid_type():
    with pytest.raises(ValidationError):
        ScannedNode(id="x", flow="f", type="generic")


def test_scanned_node_rejects_missing_required():
    with pytest.raises(ValidationError):
        ScannedNode(id="x", type="act")  # missing flow

    with pytest.raises(ValidationError):
        ScannedNode(flow="f", type="act")  # missing id


def test_scan_upload_payload_valid():
    payload = ScanUploadPayload(
        scanned_at="2026-03-25T12:00:00Z",
        files_scanned=5,
        flows={
            "checkout": [
                ScannedNode(id="start", flow="checkout", type="act"),
                ScannedNode(
                    id="pay",
                    flow="checkout",
                    type="assert",
                    dep_ids=["start"],
                ),
            ],
            "refund": [
                ScannedNode(id="refund_start", flow="refund", type="act"),
            ],
        },
    )
    assert payload.version == "1.0"
    assert payload.files_scanned == 5
    assert len(payload.flows) == 2
    assert len(payload.flows["checkout"]) == 2
    assert len(payload.flows["refund"]) == 1


def test_scan_upload_payload_empty_flows():
    payload = ScanUploadPayload(
        scanned_at="2026-03-25T12:00:00Z",
        files_scanned=0,
        flows={},
    )
    assert payload.flows == {}


def test_scan_upload_payload_missing_required():
    with pytest.raises(ValidationError):
        ScanUploadPayload(
            scanned_at="2026-03-25T12:00:00Z",
            # missing files_scanned
            flows={},
        )


def test_scan_upload_response():
    resp = ScanUploadResponse(
        created=3,
        updated=1,
        deleted=2,
        flows=["checkout", "refund"],
    )
    assert resp.created == 3
    assert resp.updated == 1
    assert resp.deleted == 2
    assert resp.flows == ["checkout", "refund"]


def test_scan_upload_response_serialization():
    resp = ScanUploadResponse(
        created=0,
        updated=0,
        deleted=0,
        flows=[],
    )
    data = resp.model_dump()
    assert data == {
        "created": 0,
        "updated": 0,
        "deleted": 0,
        "flows": [],
    }


# ---------------------------------------------------------------------------
# Integration tests — hit the actual POST /v1/nodes/scan endpoint
# ---------------------------------------------------------------------------

TEST_API_KEY = "test-key-12345"


async def _no_op_api_key() -> None:
    """Bypass API key check for authenticated tests."""
    return None


@pytest_asyncio.fixture
async def test_session_factory():
    """Create an in-memory SQLite engine and tables for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    factory = async_sessionmaker(
        expire_on_commit=False,
        autoflush=True,
        bind=engine,
    )
    yield factory

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(test_session_factory, monkeypatch):
    """Authenticated async test client with in-memory DB."""
    import src.db.transactional as txn_module

    monkeypatch.setattr(txn_module, "AsyncSessionLocal", test_session_factory)

    app.dependency_overrides[ensure_api_key] = _no_op_api_key
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def unauth_client(test_session_factory, monkeypatch):
    """Unauthenticated async test client (no API key override)."""
    import src.db.transactional as txn_module

    monkeypatch.setattr(txn_module, "AsyncSessionLocal", test_session_factory)

    app.dependency_overrides.pop(ensure_api_key, None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def _make_payload(flows: dict[str, list[dict]]) -> dict:
    return {
        "version": "1.0",
        "scanned_at": "2026-03-25T12:00:00Z",
        "files_scanned": 1,
        "flows": flows,
    }


# --- Create ---


@pytest.mark.asyncio
async def test_create_nodes(client, test_session_factory):
    """POST creates new nodes with source='scan'."""
    payload = _make_payload(
        {
            "checkout": [
                {"id": "cart_created", "flow": "checkout", "type": "act"},
                {
                    "id": "payment_ok",
                    "flow": "checkout",
                    "type": "assert",
                    "dep_ids": ["cart_created"],
                },
            ]
        }
    )

    resp = await client.post("/v1/nodes/scan", json=payload)
    assert resp.status_code == 200

    data = resp.json()
    assert data["created"] == 2
    assert data["updated"] == 0
    assert data["deleted"] == 0
    assert "checkout" in data["flows"]

    # Verify DB state
    async with test_session_factory() as s:
        nodes = (await s.execute(select(Node))).scalars().all()
        assert len(nodes) == 2
        by_id = {n.id: n for n in nodes}
        assert by_id["cart_created"].source == "scan"
        assert by_id["cart_created"].flow == "checkout"
        assert by_id["cart_created"].type == "act"
        assert by_id["payment_ok"].dep_ids == ["cart_created"]


# --- Update ---


@pytest.mark.asyncio
async def test_update_nodes(client, test_session_factory):
    """Re-POSTing with changed properties updates existing nodes."""
    # First scan — create
    payload1 = _make_payload(
        {
            "checkout": [
                {"id": "cart_created", "flow": "checkout", "type": "act"},
            ]
        }
    )
    resp1 = await client.post("/v1/nodes/scan", json=payload1)
    assert resp1.json()["created"] == 1

    # Second scan — update with new description
    payload2 = _make_payload(
        {
            "checkout": [
                {
                    "id": "cart_created",
                    "flow": "checkout",
                    "type": "act",
                    "description": "Cart was created",
                },
            ]
        }
    )
    resp2 = await client.post("/v1/nodes/scan", json=payload2)
    data2 = resp2.json()
    assert data2["created"] == 0
    assert data2["updated"] == 1
    assert data2["deleted"] == 0

    # Verify DB state
    async with test_session_factory() as s:
        node = await s.get(Node, "cart_created")
        assert node is not None
        assert node.description == "Cart was created"
        assert node.source == "scan"
        assert node.updated_at is not None


# --- Stale node cleanup ---


@pytest.mark.asyncio
async def test_stale_node_soft_deleted(client, test_session_factory):
    """Nodes from a previous scan that are missing in a new scan get soft-deleted."""
    # First scan — create two nodes
    payload1 = _make_payload(
        {
            "checkout": [
                {"id": "cart_created", "flow": "checkout", "type": "act"},
                {
                    "id": "payment_ok",
                    "flow": "checkout",
                    "type": "assert",
                    "dep_ids": ["cart_created"],
                },
            ]
        }
    )
    resp1 = await client.post("/v1/nodes/scan", json=payload1)
    assert resp1.json()["created"] == 2

    # Second scan — only cart_created remains
    payload2 = _make_payload(
        {
            "checkout": [
                {"id": "cart_created", "flow": "checkout", "type": "act"},
            ]
        }
    )
    resp2 = await client.post("/v1/nodes/scan", json=payload2)
    data2 = resp2.json()
    assert data2["updated"] == 1  # cart_created re-scanned
    assert data2["deleted"] == 1  # payment_ok soft-deleted

    # Verify DB state — payment_ok should have deleted_at set
    async with test_session_factory() as s:
        payment_node = await s.get(Node, "payment_ok")
        assert payment_node is not None
        assert payment_node.deleted_at is not None

        cart_node = await s.get(Node, "cart_created")
        assert cart_node is not None
        assert cart_node.deleted_at is None


# --- Manual nodes unaffected ---


@pytest.mark.asyncio
async def test_manual_nodes_unaffected(client, test_session_factory):
    """Scan upsert must not touch nodes with source != 'scan'."""
    from src.utils.time import now

    # Seed a manual node
    async with test_session_factory() as s:
        async with s.begin():
            manual_node = Node(
                id="manual_step",
                flow="checkout",
                type="act",
                source="manual",
                created_at=now(),
                status="active",
            )
            s.add(manual_node)

    # Scan the same flow without manual_step
    payload = _make_payload(
        {
            "checkout": [
                {"id": "scan_step", "flow": "checkout", "type": "act"},
            ]
        }
    )
    resp = await client.post("/v1/nodes/scan", json=payload)
    assert resp.json()["created"] == 1
    assert resp.json()["deleted"] == 0  # manual node not deleted

    # Verify manual node is untouched
    async with test_session_factory() as s:
        manual = await s.get(Node, "manual_step")
        assert manual is not None
        assert manual.source == "manual"
        assert manual.deleted_at is None


# --- Auth enforcement ---


@pytest.mark.asyncio
async def test_no_api_key_returns_401(unauth_client):
    """POST without API key returns 401."""
    payload = _make_payload(
        {
            "checkout": [
                {"id": "x", "flow": "checkout", "type": "act"},
            ]
        }
    )
    resp = await unauth_client.post("/v1/nodes/scan", json=payload)
    assert resp.status_code == 401
