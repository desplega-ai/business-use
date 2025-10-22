"""YAML loader for node definitions.

Supports loading and exporting node definitions in YAML format,
following infrastructure-as-code patterns.
"""

from pathlib import Path
from typing import Any

import yaml

from src.api.models import NodeYAMLCreateSchema as NodeCreateSchema
from src.models import ActionInput, ActionInputParams, Expr, NodeCondition


class YAMLNodeDefinition:
    """Represents a node definition loaded from YAML."""

    def __init__(self, flow: str, node_data: dict[str, Any]):
        self.flow = flow
        self.node_data = node_data

    def to_create_schema(self) -> NodeCreateSchema:
        """Convert to NodeCreateSchema for database operations."""
        # Parse filter if present
        filter_data = self.node_data.get("filter")
        filter_obj = Expr(**filter_data) if filter_data else None

        # Parse validator if present
        validator_data = self.node_data.get("validator")
        validator_obj = Expr(**validator_data) if validator_data else None

        # Parse conditions if present
        conditions_data = self.node_data.get("conditions", [])
        conditions_obj = [NodeCondition(**cond) for cond in conditions_data]

        # Parse handler_input if present
        handler_input_data = self.node_data.get("handler_input")
        handler_input_obj = None
        if handler_input_data:
            # Parse params if present
            params_data = handler_input_data.get("params")
            params_obj = None
            if params_data:
                # Parse run_id_extractor if present in params
                run_id_extractor_data = params_data.get("run_id_extractor")
                run_id_extractor_obj = (
                    Expr(**run_id_extractor_data) if run_id_extractor_data else None
                )

                params_obj = ActionInputParams(
                    url=params_data.get("url"),
                    method=params_data.get("method"),
                    headers=params_data.get("headers"),
                    body=params_data.get("body"),
                    timeout_ms=params_data.get("timeout_ms"),
                    test_run_id=params_data.get("test_run_id"),
                    test_suite_run_id=params_data.get("test_suite_run_id"),
                    command=params_data.get("command"),
                    run_id_extractor=run_id_extractor_obj,
                )

            handler_input_obj = ActionInput(
                input_schema=handler_input_data.get("input_schema"),
                params=params_obj,
            )

        return NodeCreateSchema(
            flow=self.flow,
            id=self.node_data["id"],
            type=self.node_data["type"],
            description=self.node_data.get("description"),
            dep_ids=self.node_data.get("dep_ids", []),
            filter=filter_obj,
            validator=validator_obj,
            conditions=conditions_obj if conditions_obj else None,
            handler=self.node_data.get("handler"),
            handler_input=handler_input_obj,
            additional_meta=self.node_data.get("additional_meta"),
        )


def load_nodes_from_yaml(file_path: str | Path) -> list[YAMLNodeDefinition]:
    """Load node definitions from a YAML file.

    Args:
        file_path: Path to the YAML file

    Returns:
        List of YAMLNodeDefinition objects

    Raises:
        FileNotFoundError: If the file doesn't exist
        yaml.YAMLError: If the YAML is malformed
        ValueError: If the YAML structure is invalid
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"YAML file not found: {file_path}")

    with file_path.open("r") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("YAML root must be a dictionary")

    flow = data.get("flow")
    if not flow:
        raise ValueError("YAML must contain a 'flow' field")

    nodes = data.get("nodes", [])
    if not isinstance(nodes, list):
        raise ValueError("'nodes' field must be a list")

    node_defs = []
    for node_data in nodes:
        if not isinstance(node_data, dict):
            raise ValueError("Each node must be a dictionary")

        if "id" not in node_data:
            raise ValueError("Each node must have an 'id' field")

        if "type" not in node_data:
            raise ValueError("Each node must have a 'type' field")

        node_defs.append(YAMLNodeDefinition(flow, node_data))

    return node_defs


def export_nodes_to_yaml(flow: str, nodes: list[dict[str, Any]]) -> str:
    """Export nodes to YAML format.

    Args:
        flow: Flow identifier
        nodes: List of node dictionaries (from database)

    Returns:
        YAML string representation
    """
    yaml_data: dict[str, Any] = {"flow": flow, "nodes": []}

    for node in nodes:
        node_dict: dict[str, Any] = {
            "id": node["id"],
            "type": node["type"],
        }

        # Optional fields
        if node.get("description"):
            node_dict["description"] = node["description"]

        if node.get("dep_ids"):
            node_dict["dep_ids"] = node["dep_ids"]

        if node.get("filter"):
            filter_obj = node["filter"]
            if isinstance(filter_obj, dict):
                node_dict["filter"] = filter_obj
            else:
                node_dict["filter"] = {
                    "engine": filter_obj.engine,
                    "script": filter_obj.script,
                }

        if node.get("validator"):
            validator_obj = node["validator"]
            if isinstance(validator_obj, dict):
                node_dict["validator"] = validator_obj
            else:
                node_dict["validator"] = {
                    "engine": validator_obj.engine,
                    "script": validator_obj.script,
                }

        if node.get("conditions"):
            conditions = node["conditions"]
            if conditions:
                node_dict["conditions"] = []
                for cond in conditions:
                    if isinstance(cond, dict):
                        node_dict["conditions"].append(cond)
                    else:
                        cond_dict = {}
                        if hasattr(cond, "timeout_ms") and cond.timeout_ms is not None:
                            cond_dict["timeout_ms"] = cond.timeout_ms
                        if cond_dict:
                            node_dict["conditions"].append(cond_dict)

        if node.get("handler"):
            node_dict["handler"] = node["handler"]

        if node.get("handler_input"):
            node_dict["handler_input"] = node["handler_input"]

        if node.get("additional_meta"):
            node_dict["additional_meta"] = node["additional_meta"]

        yaml_data["nodes"].append(node_dict)

    result = yaml.dump(yaml_data, default_flow_style=False, sort_keys=False)
    return str(result)


def validate_yaml_file(file_path: str | Path) -> tuple[bool, str | None]:
    """Validate a YAML file without loading it into the database.

    Args:
        file_path: Path to the YAML file

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        node_defs = load_nodes_from_yaml(file_path)

        # Try to convert each to NodeCreateSchema to validate structure
        for node_def in node_defs:
            node_def.to_create_schema()

        return True, None
    except Exception as e:
        return False, str(e)
