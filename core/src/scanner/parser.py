"""Tree-sitter parsing: language detection and AST construction."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Language, Tree


def _check_tree_sitter() -> None:
    """Check that tree-sitter dependencies are installed."""
    try:
        import tree_sitter  # noqa: F401
        import tree_sitter_javascript  # noqa: F401
        import tree_sitter_typescript  # noqa: F401
    except ImportError as e:
        raise SystemExit(
            "Scanner requires tree-sitter dependencies.\n"
            "Install with: pip install 'business-use-core[scan]'\n"
            "Or with uvx: uvx --with 'business-use-core[scan]' business-use-core scan ..."
        ) from e


def get_language(filepath: str) -> Language:
    """Get the tree-sitter Language for a file based on its extension."""
    import tree_sitter_javascript as tsjs
    import tree_sitter_typescript as tsts
    from tree_sitter import Language

    ext = Path(filepath).suffix
    if ext == ".tsx":
        return Language(tsts.language_tsx())
    if ext in (".ts", ".mts"):
        return Language(tsts.language_typescript())
    return Language(tsjs.language())  # .js, .jsx, .mjs


def parse_file(filepath: str) -> Tree:
    """Parse a JS/TS file and return the tree-sitter Tree."""
    from tree_sitter import Parser

    source = Path(filepath).read_bytes()
    lang = get_language(filepath)
    parser = Parser(lang)
    return parser.parse(source)


# Supported file extensions for scanning
SCAN_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".mts", ".mjs"}
