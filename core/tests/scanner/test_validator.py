"""Test graph validation: broken refs, duplicates, unreachable nodes."""

from src.scanner.models import ExtractedNode
from src.scanner.validator import validate_graph


def _node(
    id: str,
    flow: str = "test",
    dep_ids: list[str] | None = None,
    source_file: str = "test.ts",
    source_line: int = 1,
) -> ExtractedNode:
    return ExtractedNode(
        id=id,
        flow=flow,
        type="act",
        dep_ids=dep_ids or [],
        source_file=source_file,
        source_line=source_line,
    )


def test_valid_graph():
    flows = {
        "checkout": [
            _node("root", dep_ids=[]),
            _node("child", dep_ids=["root"]),
        ]
    }
    warnings = validate_graph(flows)
    assert len(warnings) == 0


def test_broken_dep_ids_reference():
    flows = {
        "checkout": [
            _node("root"),
            _node("child", dep_ids=["nonexistent"]),
        ]
    }
    warnings = validate_graph(flows)
    # Broken dep ref + unreachable (since dep doesn't exist, can't reach from root)
    assert len(warnings) == 2
    messages = [w.message for w in warnings]
    assert any("nonexistent" in m for m in messages)
    assert any("unreachable" in m for m in messages)


def test_duplicate_node_ids():
    flows = {
        "checkout": [
            _node("root"),
            _node("root", source_line=10),
        ]
    }
    warnings = validate_graph(flows)
    assert any("Duplicate" in w.message for w in warnings)


def test_unreachable_node():
    flows = {
        "checkout": [
            _node("root"),
            _node("child", dep_ids=["root"]),
            _node("orphan", dep_ids=["missing"]),
        ]
    }
    warnings = validate_graph(flows)
    # Should warn about missing dep_id AND orphan being unreachable
    messages = [w.message for w in warnings]
    assert any("missing" in m for m in messages)


def test_no_root_nodes():
    flows = {
        "checkout": [
            _node("a", dep_ids=["b"]),
            _node("b", dep_ids=["a"]),
        ]
    }
    warnings = validate_graph(flows)
    assert any("no root nodes" in w.message for w in warnings)


def test_empty_flows():
    warnings = validate_graph({})
    assert len(warnings) == 0


def test_multiple_flows_validated_independently():
    flows = {
        "flow_a": [
            _node("root", flow="flow_a"),
            _node("child", flow="flow_a", dep_ids=["root"]),
        ],
        "flow_b": [
            _node("root", flow="flow_b"),
            _node("child", flow="flow_b", dep_ids=["nonexistent"]),
        ],
    }
    warnings = validate_graph(flows)
    # Only flow_b should have warnings (broken ref + unreachable)
    assert len(warnings) == 2
    assert all("flow_b" in w.message for w in warnings)
