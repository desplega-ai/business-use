"""Scanner module: statically analyze JS/TS codebases to extract SDK call sites."""

from pathlib import Path

from src.scanner.models import ExtractedNode, ScanResult, ScanWarning
from src.scanner.parser import SCAN_EXTENSIONS, _check_tree_sitter
from src.scanner.validator import validate_graph

__all__ = [
    "ExtractedNode",
    "ScanResult",
    "ScanWarning",
    "scan_directory",
    "scan_files",
    "validate_graph",
]


def scan_files(paths: list[Path]) -> ScanResult:
    """Scan specific JS/TS files for SDK calls."""
    _check_tree_sitter()
    from src.scanner.extractor import scan_file

    result = ScanResult()

    for path in paths:
        filepath = str(path)
        result.files_scanned += 1

        nodes, warnings, skipped = scan_file(filepath)
        if skipped:
            result.files_skipped += 1
            continue

        result.warnings.extend(warnings)
        for node in nodes:
            if node.flow not in result.flows:
                result.flows[node.flow] = []
            result.flows[node.flow].append(node)

    return result


def scan_directory(
    path: Path,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> ScanResult:
    """Scan a directory for JS/TS files containing SDK calls."""
    _check_tree_sitter()

    exclude = exclude or ["node_modules"]
    allowed_extensions = set(include) if include else SCAN_EXTENSIONS
    files = sorted(
        p
        for p in path.rglob("*")
        if p.suffix in allowed_extensions and not any(ex in str(p) for ex in exclude)
    )

    return scan_files(files)
