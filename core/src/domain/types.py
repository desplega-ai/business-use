"""TypedDict definitions for domain return values.

These are lightweight alternatives to Pydantic models for internal use.
"""

from typing import Any, TypedDict

from src.models import EvalStatus


# Type definitions for validator and filter context
class DepData(TypedDict):
    """Upstream dependency event data.

    Attributes:
        flow: Flow identifier
        id: Node/event identifier
        data: Event data payload
    """

    flow: str
    id: str
    data: dict[str, Any]


class Ctx(TypedDict):
    """Context passed to filter and validator functions.

    Attributes:
        deps: List of upstream dependency event data
    """

    deps: list[DepData]


class FlowGraph(TypedDict):
    """Graph representation of flow nodes and their dependencies.

    Attributes:
        graph: Adjacency list mapping node_id -> [dependent_node_ids]
        nodes: Map of node_id -> Node object for quick lookup
    """

    graph: dict[str, list[str]]
    nodes: dict[str, Any]  # node_id -> Node


class LayeredEvents(TypedDict):
    """Events matched to graph layers for execution.

    Attributes:
        layers: List of layers, each containing list of event IDs
        events: Map of event_id -> Event object for quick lookup
    """

    layers: list[list[str]]  # List of layers with event IDs
    events: dict[str, Any]  # event_id -> Event


class ValidationItem(TypedDict, total=False):
    """Single validation result item.

    Attributes:
        node_id: Node identifier
        dep_node_ids: Dependency node IDs
        status: Validation status
        message: Optional success/info message
        error: Optional error message
        elapsed_ns: Time taken in nanoseconds
        ev_ids: Event IDs for this node
        upstream_ev_ids: Upstream event IDs
    """

    node_id: str
    dep_node_ids: list[str]
    status: EvalStatus
    message: str | None
    error: str | None
    elapsed_ns: int
    ev_ids: list[str]
    upstream_ev_ids: list[str]


class ValidationResult(TypedDict):
    """Result of flow validation.

    Attributes:
        status: Overall evaluation status
        items: List of validation items per node
        elapsed_ns: Total time taken
        graph: The graph that was evaluated
        ev_ids: All event IDs involved
    """

    status: EvalStatus
    items: list[ValidationItem]
    elapsed_ns: int
    graph: dict[str, list[str]]
    ev_ids: list[str]
