"""
Proof-of-concept: py-tree-sitter scanner for business-use SDK calls.
Tests against the JS/TS fixtures in e2e-tests/js/.
"""

import json
import sys
from pathlib import Path

import tree_sitter_javascript as tsjs
import tree_sitter_typescript as tsts
from tree_sitter import Language, Parser, Node

JS_LANGUAGE = Language(tsjs.language())
TS_LANGUAGE = Language(tsts.language_typescript())
TSX_LANGUAGE = Language(tsts.language_tsx())

TARGET_FUNCTIONS = {"ensure", "act", "assert"}
TARGET_MODULES = {"business-use", "business_use"}


def get_language(filepath: str) -> Language:
    ext = Path(filepath).suffix
    if ext == ".tsx":
        return TSX_LANGUAGE
    if ext in (".ts", ".mts"):
        return TS_LANGUAGE
    return JS_LANGUAGE  # .js, .jsx, .mjs


def get_string_value(node: Node) -> str | None:
    """Extract string value from a string node (handles quotes)."""
    if node.type == "string":
        # String node children: string_fragment (the content without quotes)
        for child in node.children:
            if child.type == "string_fragment":
                return child.text.decode("utf-8")
        # Empty string case
        return ""
    if node.type == "template_string":
        # Only handle no-substitution template literals
        fragments = [c for c in node.children if c.type == "string_fragment"]
        substitutions = [c for c in node.children if c.type == "template_substitution"]
        if not substitutions and fragments:
            return fragments[0].text.decode("utf-8")
    return None


def extract_imports(root: Node) -> dict:
    """
    Find imports from business-use and return info about what was imported.
    Returns: {
        'named': set of directly imported names,
        'aliases': dict of local_name -> original_name,
        'namespace': namespace identifier or None,
    }
    """
    result = {"named": set(), "aliases": {}, "namespace": None}

    for node in root.children:
        if node.type != "import_statement":
            continue

        # Find module source
        source_node = node.child_by_field_name("source")
        if not source_node:
            continue
        module_name = get_string_value(source_node)
        if module_name not in TARGET_MODULES:
            continue

        # Walk import clause for named/namespace imports
        for child in _walk(node):
            if child.type == "import_specifier":
                name_node = child.child_by_field_name("name")
                alias_node = child.child_by_field_name("alias")
                if name_node:
                    original = name_node.text.decode("utf-8")
                    if original in TARGET_FUNCTIONS:
                        if alias_node:
                            local = alias_node.text.decode("utf-8")
                            result["aliases"][local] = original
                        else:
                            result["named"].add(original)

            if child.type == "namespace_import":
                for c in child.children:
                    if c.type == "identifier":
                        result["namespace"] = c.text.decode("utf-8")

    return result


def _walk(node: Node):
    """Yield all descendants of a node."""
    for child in node.children:
        yield child
        yield from _walk(child)


def is_target_call(node: Node, imports: dict) -> str | None:
    """
    Check if a call_expression is a target SDK call.
    Returns the canonical function name (ensure/act/assert) or None.
    """
    fn_node = node.child_by_field_name("function")
    if not fn_node:
        return None

    # Direct call: ensure({...})
    if fn_node.type == "identifier":
        name = fn_node.text.decode("utf-8")
        if name in imports["named"]:
            return name
        if name in imports["aliases"]:
            return imports["aliases"][name]
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
            obj_name = obj.text.decode("utf-8")
            prop_name = prop.text.decode("utf-8")
            if obj_name == imports["namespace"] and prop_name in TARGET_FUNCTIONS:
                return prop_name

    return None


def extract_object_props(obj_node: Node) -> dict:
    """Extract properties from an object literal argument."""
    result = {
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

        key = key_node.text.decode("utf-8")

        if key == "id":
            val = get_string_value(value_node)
            if val is not None:
                result["id"] = val
            else:
                result["warnings"].append(
                    f"'id' is not a string literal ({value_node.type})"
                )

        elif key == "flow":
            val = get_string_value(value_node)
            if val is not None:
                result["flow"] = val
            else:
                result["warnings"].append(
                    f"'flow' is not a string literal ({value_node.type})"
                )

        elif key == "depIds" or key == "dep_ids":
            if value_node.type == "array":
                for elem in value_node.children:
                    if elem.type in ("string", "template_string"):
                        val = get_string_value(elem)
                        if val is not None:
                            result["dep_ids"].append(val)
                        else:
                            result["warnings"].append(
                                f"depIds contains non-extractable element"
                            )
                    elif elem.type == "identifier":
                        result["warnings"].append(
                            f"depIds contains variable '{elem.text.decode()}'"
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
            val = get_string_value(value_node)
            if val is not None:
                result["description"] = val

        elif key == "conditions":
            if value_node.type == "array":
                # Try to extract timeout_ms from object literals
                for elem in value_node.children:
                    if elem.type == "object":
                        for pair in elem.children:
                            if pair.type == "pair":
                                pk = pair.child_by_field_name("key")
                                pv = pair.child_by_field_name("value")
                                if pk and pv and pk.text == b"timeout_ms":
                                    if pv.type == "number":
                                        result["conditions"].append(
                                            {"timeout_ms": int(pv.text.decode())}
                                        )

    return result


def scan_file(filepath: str) -> dict:
    """Scan a single JS/TS file for SDK calls."""
    source = Path(filepath).read_bytes()
    lang = get_language(filepath)

    parser = Parser(lang)
    tree = parser.parse(source)
    root = tree.root_node

    # Step 1: Check imports
    imports = extract_imports(root)
    if not imports["named"] and not imports["aliases"] and not imports["namespace"]:
        return {"file": filepath, "nodes": [], "skipped": True}

    # Step 2: Find all call expressions
    nodes = []
    warnings = []

    for node in _walk(root):
        if node.type != "call_expression":
            continue

        fn_name = is_target_call(node, imports)
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
                f"{filepath}:{node.start_point[0]+1} - {fn_name}() called without object literal argument"
            )
            continue

        props = extract_object_props(obj_node)

        if not props["id"] or not props["flow"]:
            file_warnings = []
            if not props["id"]:
                file_warnings.append("missing/non-literal 'id'")
            if not props["flow"]:
                file_warnings.append("missing/non-literal 'flow'")
            warnings.append(
                f"{filepath}:{node.start_point[0]+1} - {fn_name}() skipped: {', '.join(file_warnings)}"
            )
            continue

        # Determine type
        if fn_name == "assert":
            node_type = "assert"
        elif fn_name == "act":
            node_type = "act"
        else:  # ensure
            node_type = "assert" if props["has_validator"] else "act"

        extracted = {
            "id": props["id"],
            "flow": props["flow"],
            "type": node_type,
            "dep_ids": props["dep_ids"],
            "has_validator": props["has_validator"],
            "has_filter": props["has_filter"],
            "source": {
                "file": filepath,
                "line": node.start_point[0] + 1,
                "column": node.start_point[1] + 1,
            },
        }
        if props["description"]:
            extracted["description"] = props["description"]
        if props["conditions"]:
            extracted["conditions"] = props["conditions"]
        if props["warnings"]:
            extracted["warnings"] = props["warnings"]
            for w in props["warnings"]:
                warnings.append(f"{filepath}:{node.start_point[0]+1} - {w}")

        nodes.append(extracted)

    return {"file": filepath, "nodes": nodes, "warnings": warnings, "skipped": False}


def scan_directory(dirpath: str) -> dict:
    """Scan all JS/TS files in a directory."""
    extensions = {".ts", ".tsx", ".js", ".jsx", ".mts", ".mjs"}
    files = sorted(
        p
        for p in Path(dirpath).rglob("*")
        if p.suffix in extensions and "node_modules" not in str(p)
    )

    all_nodes = []
    all_warnings = []
    files_scanned = 0
    files_skipped = 0

    for f in files:
        result = scan_file(str(f))
        files_scanned += 1
        if result.get("skipped"):
            files_skipped += 1
            continue
        all_nodes.extend(result["nodes"])
        all_warnings.extend(result.get("warnings", []))

    # Group by flow
    flows = {}
    for node in all_nodes:
        flow = node["flow"]
        if flow not in flows:
            flows[flow] = {"nodes": []}
        flows[flow]["nodes"].append(node)

    return {
        "version": "1.0",
        "files_scanned": files_scanned,
        "files_skipped": files_skipped,
        "flows": flows,
        "warnings": all_warnings,
    }


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "e2e-tests/js"
    result = scan_directory(target)
    print(json.dumps(result, indent=2))
