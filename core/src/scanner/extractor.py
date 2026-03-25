"""Node extraction from JS/TS AST: find SDK call sites and extract properties."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.scanner.imports import (
    TARGET_FUNCTIONS,
    ImportInfo,
    _get_string_value,
    _walk,
    extract_imports,
)
from src.scanner.models import ExtractedNode, ScanWarning
from src.scanner.parser import parse_file

if TYPE_CHECKING:
    from tree_sitter import Node


def _is_target_call(node: Node, imports: ImportInfo) -> str | None:
    """Check if a call_expression is a target SDK call.

    Returns the canonical function name (ensure/act/assert) or None.
    """
    fn_node = node.child_by_field_name("function")
    if not fn_node:
        return None

    # Direct call: ensure({...})
    if fn_node.type == "identifier" and fn_node.text is not None:
        name = fn_node.text.decode("utf-8")
        if name in imports.named:
            return name
        if name in imports.aliases:
            return imports.aliases[name]
        return None

    # Member expression: bu.ensure({...})
    if fn_node.type == "member_expression":
        obj = fn_node.child_by_field_name("object")
        prop = fn_node.child_by_field_name("property")
        if (
            obj
            and prop
            and obj.type == "identifier"
            and prop.type == "property_identifier"
        ):
            obj_name = obj.text.decode("utf-8") if obj.text else ""
            prop_name = prop.text.decode("utf-8") if prop.text else ""
            if obj_name == imports.namespace and prop_name in TARGET_FUNCTIONS:
                return prop_name

    return None


def _extract_object_props(obj_node: Node) -> dict[str, Any]:
    """Extract properties from an object literal argument."""
    result: dict[str, Any] = {
        "id": None,
        "flow": None,
        "dep_ids": [],
        "has_validator": False,
        "has_filter": False,
        "description": None,
        "conditions": [],
        "warnings": [],
    }

    for child in obj_node.children:
        if child.type != "pair":
            continue

        key_node = child.child_by_field_name("key")
        value_node = child.child_by_field_name("value")
        if not key_node or not value_node:
            continue

        key = key_node.text.decode("utf-8") if key_node.text else ""

        if key == "id":
            val = _get_string_value(value_node)
            if val is not None:
                result["id"] = val
            else:
                result["warnings"].append(
                    f"'id' is not a string literal ({value_node.type})"
                )

        elif key == "flow":
            val = _get_string_value(value_node)
            if val is not None:
                result["flow"] = val
            else:
                result["warnings"].append(
                    f"'flow' is not a string literal ({value_node.type})"
                )

        elif key in ("depIds", "dep_ids"):
            if value_node.type == "array":
                for elem in value_node.children:
                    if elem.type in ("string", "template_string"):
                        val = _get_string_value(elem)
                        if val is not None:
                            result["dep_ids"].append(val)
                        else:
                            result["warnings"].append(
                                "depIds contains non-extractable element"
                            )
                    elif elem.type == "identifier":
                        elem_text = elem.text.decode() if elem.text else "?"
                        result["warnings"].append(
                            f"depIds contains variable '{elem_text}'"
                        )
                    elif elem.type == "spread_element":
                        result["warnings"].append("depIds contains spread element")
            else:
                result["warnings"].append(
                    f"depIds is not an array literal ({value_node.type})"
                )

        elif key == "validator":
            result["has_validator"] = True

        elif key == "filter":
            result["has_filter"] = True

        elif key == "description":
            val = _get_string_value(value_node)
            if val is not None:
                result["description"] = val

        elif key == "conditions":
            if value_node.type == "array":
                for elem in value_node.children:
                    if elem.type == "object":
                        for pair in elem.children:
                            if pair.type == "pair":
                                pk = pair.child_by_field_name("key")
                                pv = pair.child_by_field_name("value")
                                if pk and pv and pk.text == b"timeout_ms":
                                    if pv.type == "number" and pv.text is not None:
                                        result["conditions"].append(
                                            {"timeout_ms": int(pv.text.decode())}
                                        )

    return result


def scan_file(filepath: str) -> tuple[list[ExtractedNode], list[ScanWarning], bool]:
    """Scan a single JS/TS file for SDK calls.

    Returns:
        Tuple of (extracted_nodes, warnings, was_skipped).
        was_skipped is True if the file had no business-use imports.
    """
    tree = parse_file(filepath)
    root = tree.root_node

    # Step 1: Check imports
    imports = extract_imports(root)
    if not imports.has_imports:
        return [], [], True

    # Step 2: Find all call expressions
    nodes: list[ExtractedNode] = []
    warnings: list[ScanWarning] = []

    for node in _walk(root):
        if node.type != "call_expression":
            continue

        fn_name = _is_target_call(node, imports)
        if fn_name is None:
            continue

        # Get the first argument (object literal)
        args_node = node.child_by_field_name("arguments")
        if not args_node:
            continue

        # Find first object argument
        obj_node = None
        for arg_child in args_node.children:
            if arg_child.type == "object":
                obj_node = arg_child
                break

        if not obj_node:
            warnings.append(
                ScanWarning(
                    file=filepath,
                    line=node.start_point[0] + 1,
                    message=f"{fn_name}() called without object literal argument",
                )
            )
            continue

        props = _extract_object_props(obj_node)

        if not props["id"] or not props["flow"]:
            parts = []
            if not props["id"]:
                parts.append("missing/non-literal 'id'")
            if not props["flow"]:
                parts.append("missing/non-literal 'flow'")
            warnings.append(
                ScanWarning(
                    file=filepath,
                    line=node.start_point[0] + 1,
                    message=f"{fn_name}() skipped: {', '.join(parts)}",
                )
            )
            continue

        # Determine type
        if fn_name == "assert":
            node_type = "assert"
        elif fn_name == "act":
            node_type = "act"
        else:  # ensure
            node_type = "assert" if props["has_validator"] else "act"

        extracted = ExtractedNode(
            id=props["id"],
            flow=props["flow"],
            type=node_type,
            dep_ids=props["dep_ids"],
            has_validator=props["has_validator"],
            has_filter=props["has_filter"],
            description=props["description"],
            conditions=props["conditions"],
            source_file=filepath,
            source_line=node.start_point[0] + 1,
            source_column=node.start_point[1] + 1,
            warnings=props["warnings"],
        )

        # Propagate property-level warnings
        for w in props["warnings"]:
            warnings.append(
                ScanWarning(
                    file=filepath,
                    line=node.start_point[0] + 1,
                    message=w,
                )
            )

        nodes.append(extracted)

    return nodes, warnings, False
