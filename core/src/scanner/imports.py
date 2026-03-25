"""Import analysis: detect business-use SDK imports in JS/TS files."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Node

TARGET_FUNCTIONS = {"ensure", "act", "assert"}
TARGET_MODULES = {"business-use", "business_use", "@desplega.ai/business-use"}


def _walk(node: Node):
    """Yield all descendants of a node."""
    for child in node.children:
        yield child
        yield from _walk(child)


def _get_string_value(node: Node) -> str | None:
    """Extract string value from a string node (handles quotes)."""
    if node.type == "string":
        for child in node.children:
            if child.type == "string_fragment" and child.text is not None:
                return child.text.decode("utf-8")
        return ""
    if node.type == "template_string":
        fragments = [c for c in node.children if c.type == "string_fragment"]
        substitutions = [c for c in node.children if c.type == "template_substitution"]
        if not substitutions and fragments and fragments[0].text is not None:
            return fragments[0].text.decode("utf-8")
    return None


class ImportInfo:
    """Information about business-use SDK imports found in a file."""

    def __init__(self) -> None:
        self.named: set[str] = set()
        self.aliases: dict[str, str] = {}  # local_name -> original_name
        self.namespace: str | None = None

    @property
    def has_imports(self) -> bool:
        return bool(self.named or self.aliases or self.namespace)


def extract_imports(root: Node) -> ImportInfo:
    """Find imports from business-use and return info about what was imported."""
    result = ImportInfo()

    for node in root.children:
        if node.type != "import_statement":
            continue

        source_node = node.child_by_field_name("source")
        if not source_node:
            continue
        module_name = _get_string_value(source_node)
        if module_name not in TARGET_MODULES:
            continue

        for child in _walk(node):
            if child.type == "import_specifier":
                name_node = child.child_by_field_name("name")
                alias_node = child.child_by_field_name("alias")
                if name_node and name_node.text is not None:
                    original = name_node.text.decode("utf-8")
                    if original in TARGET_FUNCTIONS:
                        if alias_node and alias_node.text is not None:
                            local = alias_node.text.decode("utf-8")
                            result.aliases[local] = original
                        else:
                            result.named.add(original)

            if child.type == "namespace_import":
                for c in child.children:
                    if c.type == "identifier" and c.text is not None:
                        result.namespace = c.text.decode("utf-8")

    return result
