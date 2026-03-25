"""Test import detection for various import patterns."""

from src.scanner.imports import extract_imports
from src.scanner.parser import parse_file


def test_named_imports(basic_flow_path: str):
    tree = parse_file(basic_flow_path)
    imports = extract_imports(tree.root_node)
    assert imports.has_imports
    assert "ensure" in imports.named or imports.aliases or imports.namespace


def test_aliased_imports(aliased_import_path: str):
    tree = parse_file(aliased_import_path)
    imports = extract_imports(tree.root_node)
    assert imports.has_imports
    assert len(imports.aliases) > 0


def test_namespace_imports(namespace_import_path: str):
    tree = parse_file(namespace_import_path)
    imports = extract_imports(tree.root_node)
    assert imports.has_imports
    assert imports.namespace is not None


def test_no_business_use_imports(no_business_use_path: str):
    tree = parse_file(no_business_use_path)
    imports = extract_imports(tree.root_node)
    assert not imports.has_imports


def test_require_pattern_no_imports(require_pattern_path: str):
    """CJS require() is not detected as an import (by design)."""
    tree = parse_file(require_pattern_path)
    imports = extract_imports(tree.root_node)
    assert not imports.has_imports
