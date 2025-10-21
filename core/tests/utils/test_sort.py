import pytest

from src.utils.sort import layered_topological_sort


def test_simple_linear_graph():
    """Test a simple linear dependency chain."""
    graph = {
        "a": ["b"],
        "b": ["c"],
        "c": [],
    }
    result = layered_topological_sort(graph)
    assert result == [["a"], ["b"], ["c"]]


def test_parallel_independent_nodes():
    """Test nodes with no dependencies execute in parallel."""
    graph = {
        "a": [],
        "b": [],
        "c": [],
    }
    result = layered_topological_sort(graph)
    assert len(result) == 1
    assert set(result[0]) == {"a", "b", "c"}


def test_diamond_pattern():
    """Test diamond dependency pattern (A -> B,C -> D)."""
    graph = {
        "a": ["b", "c"],
        "b": ["d"],
        "c": ["d"],
        "d": [],
    }
    result = layered_topological_sort(graph)
    assert result[0] == ["a"]
    assert set(result[1]) == {"b", "c"}
    assert result[2] == ["d"]


def test_complex_multilayer():
    """Test complex graph with multiple layers."""
    graph = {
        "a": ["c"],
        "b": ["c"],
        "c": ["d"],
        "d": ["e"],
        "f": ["e"],
    }
    result = layered_topological_sort(graph)
    # Layer 1: a, b, f (no dependencies)
    assert set(result[0]) == {"a", "b", "f"}
    # Layer 2: c
    assert result[1] == ["c"]
    # Layer 3: d
    assert result[2] == ["d"]
    # Layer 4: e
    assert result[3] == ["e"]


def test_graph_with_omitted_leaves():
    """Test that leaf nodes can be omitted from the graph definition."""
    graph = {
        "a": ["b", "c"],
        "b": ["d"],
    }
    result = layered_topological_sort(graph)
    assert result[0] == ["a"]
    assert set(result[1]) == {"b", "c"}
    assert result[2] == ["d"]


def test_single_node():
    """Test graph with single node."""
    graph = {"a": []}
    result = layered_topological_sort(graph)
    assert result == [["a"]]


def test_empty_graph():
    """Test empty graph."""
    graph = {}
    result = layered_topological_sort(graph)
    assert result == []


def test_cyclic_graph_raises_error():
    """Test that cyclic graphs raise ValueError."""
    graph = {
        "a": ["b"],
        "b": ["c"],
        "c": ["a"],  # Creates a cycle
    }
    with pytest.raises(ValueError, match="Graph has a cycle"):
        layered_topological_sort(graph)


def test_self_loop_raises_error():
    """Test that self-loops raise ValueError."""
    graph = {
        "a": ["a"],  # Self loop
    }
    with pytest.raises(ValueError, match="Graph has a cycle"):
        layered_topological_sort(graph)


def test_multiple_roots():
    """Test graph with multiple root nodes converging."""
    graph = {
        "root1": ["middle"],
        "root2": ["middle"],
        "root3": ["middle"],
        "middle": ["end"],
    }
    result = layered_topological_sort(graph)
    assert set(result[0]) == {"root1", "root2", "root3"}
    assert result[1] == ["middle"]
    assert result[2] == ["end"]


def test_wide_graph():
    """Test graph with many parallel branches."""
    graph = {
        "a": ["final"],
        "b": ["final"],
        "c": ["final"],
        "d": ["final"],
        "e": ["final"],
    }
    result = layered_topological_sort(graph)
    assert set(result[0]) == {"a", "b", "c", "d", "e"}
    assert result[1] == ["final"]
