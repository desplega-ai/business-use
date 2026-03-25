"""Scanner-specific types for extracted nodes and scan results."""

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class ScanWarning:
    """A warning produced during scanning."""

    file: str
    line: int | None
    message: str


@dataclass
class ExtractedNode:
    """A node extracted from a source file."""

    id: str
    flow: str
    type: str  # "act" or "assert"
    dep_ids: list[str] = field(default_factory=list)
    has_validator: bool = False
    has_filter: bool = False
    description: str | None = None
    conditions: list[dict[str, int]] = field(default_factory=list)
    source_file: str = ""
    source_line: int = 0
    source_column: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class ScanResult:
    """Result of scanning a set of files."""

    version: str = "1.0"
    scanned_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    files_scanned: int = 0
    files_skipped: int = 0
    flows: dict[str, list[ExtractedNode]] = field(default_factory=dict)
    warnings: list[ScanWarning] = field(default_factory=list)
