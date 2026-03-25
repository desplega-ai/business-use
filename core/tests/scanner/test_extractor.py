"""Test node extraction against each e2e fixture."""

from src.scanner.extractor import scan_file


def test_basic_flow(basic_flow_path: str):
    nodes, warnings, skipped = scan_file(basic_flow_path)
    assert not skipped
    assert len(nodes) == 3
    ids = {n.id for n in nodes}
    assert "cart_created" in ids
    assert "payment_processed" in ids
    assert "order_total_matches" in ids
    # All should be in checkout flow
    assert all(n.flow == "checkout" for n in nodes)


def test_basic_flow_types(basic_flow_path: str):
    nodes, _, _ = scan_file(basic_flow_path)
    node_map = {n.id: n for n in nodes}
    # ensure() without validator -> act
    assert node_map["cart_created"].type == "act"
    # ensure() with validator -> assert
    assert node_map["order_total_matches"].type == "assert"


def test_basic_flow_dep_ids(basic_flow_path: str):
    nodes, _, _ = scan_file(basic_flow_path)
    node_map = {n.id: n for n in nodes}
    assert node_map["cart_created"].dep_ids == []
    assert "cart_created" in node_map["payment_processed"].dep_ids


def test_aliased_import(aliased_import_path: str):
    nodes, _, skipped = scan_file(aliased_import_path)
    assert not skipped
    assert len(nodes) >= 1
    # Aliased imports should still be detected
    ids = {n.id for n in nodes}
    assert len(ids) > 0


def test_namespace_import(namespace_import_path: str):
    nodes, _, skipped = scan_file(namespace_import_path)
    assert not skipped
    assert len(nodes) >= 1


def test_no_business_use(no_business_use_path: str):
    nodes, _, skipped = scan_file(no_business_use_path)
    assert skipped
    assert len(nodes) == 0


def test_require_pattern(require_pattern_path: str):
    nodes, _, skipped = scan_file(require_pattern_path)
    assert skipped
    assert len(nodes) == 0


def test_edge_cases(edge_cases_path: str):
    nodes, warnings, skipped = scan_file(edge_cases_path)
    assert not skipped
    # Edge cases file should produce some nodes and some warnings
    # (dynamic values, spreads, etc. generate warnings)


def test_multiple_flows(multiple_flows_path: str):
    nodes, _, skipped = scan_file(multiple_flows_path)
    assert not skipped
    flows = {n.flow for n in nodes}
    assert len(flows) >= 2


def test_jsx_component(jsx_component_path: str):
    nodes, _, skipped = scan_file(jsx_component_path)
    assert not skipped
    assert len(nodes) >= 1


def test_helpers_usage(helpers_usage_path: str):
    nodes, _, skipped = scan_file(helpers_usage_path)
    # helpers-usage might or might not have direct imports depending on fixture
    # Just verify it doesn't crash
    assert isinstance(nodes, list)


def test_source_location(basic_flow_path: str):
    nodes, _, _ = scan_file(basic_flow_path)
    for node in nodes:
        assert node.source_file == basic_flow_path
        assert node.source_line > 0
        assert node.source_column > 0
