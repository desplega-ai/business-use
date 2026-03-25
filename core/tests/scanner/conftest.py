"""Fixtures for scanner tests."""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent.parent.parent / "e2e-tests" / "js"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def basic_flow_path(fixtures_dir: Path) -> str:
    return str(fixtures_dir / "basic-flow.ts")


@pytest.fixture
def aliased_import_path(fixtures_dir: Path) -> str:
    return str(fixtures_dir / "aliased-import.ts")


@pytest.fixture
def namespace_import_path(fixtures_dir: Path) -> str:
    return str(fixtures_dir / "namespace-import.ts")


@pytest.fixture
def no_business_use_path(fixtures_dir: Path) -> str:
    return str(fixtures_dir / "no-business-use.ts")


@pytest.fixture
def edge_cases_path(fixtures_dir: Path) -> str:
    return str(fixtures_dir / "edge-cases.ts")


@pytest.fixture
def multiple_flows_path(fixtures_dir: Path) -> str:
    return str(fixtures_dir / "multiple-flows.ts")


@pytest.fixture
def jsx_component_path(fixtures_dir: Path) -> str:
    return str(fixtures_dir / "jsx-component.tsx")


@pytest.fixture
def helpers_usage_path(fixtures_dir: Path) -> str:
    return str(fixtures_dir / "helpers-usage.ts")


@pytest.fixture
def require_pattern_path(fixtures_dir: Path) -> str:
    return str(fixtures_dir / "require-pattern.js")
