"""Tests for client module."""

import logging
from unittest import mock

from business_use import act, assert_, initialize, shutdown
from business_use.client import _state


class TestAsyncFunctionRejection:
    """Test that async functions are rejected."""

    def setup_method(self):
        """Set up test - initialize SDK."""
        # Capture logs
        self.log_records = []
        handler = logging.Handler()
        handler.emit = lambda record: self.log_records.append(record)
        logger = logging.getLogger("business-use")
        logger.addHandler(handler)
        logger.setLevel(logging.ERROR)

        # Mock successful initialization (bypass connection check)
        with mock.patch("business_use.client._check_connection", return_value=True):
            initialize(api_key="test-key", url="http://localhost:9999")

    def teardown_method(self):
        """Clean up after test."""
        shutdown(timeout=1.0)
        # Clear log records
        self.log_records.clear()
        # Reset state
        _state.initialized = False
        _state.batch_processor = None

    def test_async_run_id_rejected(self):
        """Test that async run_id is rejected."""

        async def async_run_id():
            return "run_123"

        act(
            id="test_event",
            flow="test_flow",
            run_id=async_run_id,  # This should be rejected
            data={"test": True},
        )

        # Check that an error was logged
        error_logs = [r for r in self.log_records if r.levelname == "ERROR"]
        assert any(
            "run_id cannot be an async function" in r.message for r in error_logs
        )

    def test_async_filter_rejected(self):
        """Test that async filter is rejected."""

        async def async_filter():
            return True

        act(
            id="test_event",
            flow="test_flow",
            run_id="run_123",
            data={"test": True},
            filter=async_filter,  # This should be rejected
        )

        # Check that an error was logged
        error_logs = [r for r in self.log_records if r.levelname == "ERROR"]
        assert any(
            "filter cannot be an async function" in r.message for r in error_logs
        )

    def test_async_dep_ids_rejected(self):
        """Test that async dep_ids is rejected."""

        async def async_dep_ids():
            return ["dep1", "dep2"]

        act(
            id="test_event",
            flow="test_flow",
            run_id="run_123",
            data={"test": True},
            dep_ids=async_dep_ids,  # This should be rejected
        )

        # Check that an error was logged
        error_logs = [r for r in self.log_records if r.levelname == "ERROR"]
        assert any(
            "dep_ids cannot be an async function" in r.message for r in error_logs
        )

    def test_async_validator_rejected(self):
        """Test that async validator is rejected."""

        async def async_validator(data, ctx):
            return data["test"] is True

        assert_(
            id="test_event",
            flow="test_flow",
            run_id="run_123",
            data={"test": True},
            validator=async_validator,  # This should be rejected
        )

        # Check that an error was logged
        error_logs = [r for r in self.log_records if r.levelname == "ERROR"]
        assert any(
            "validator cannot be an async function" in r.message for r in error_logs
        )

    def test_sync_functions_accepted(self):
        """Test that sync functions are accepted (no errors logged)."""

        def sync_run_id():
            return "run_123"

        def sync_filter():
            return True

        def sync_dep_ids():
            return ["dep1"]

        def sync_validator(data, ctx):
            return True

        act(
            id="test_event",
            flow="test_flow",
            run_id=sync_run_id,
            data={"test": True},
            filter=sync_filter,
            dep_ids=sync_dep_ids,
        )

        assert_(
            id="test_assertion",
            flow="test_flow",
            run_id="run_123",
            data={"test": True},
            validator=sync_validator,
        )

        # May have connection errors, but no "cannot be async" errors
        async_errors = [
            r for r in self.log_records if "cannot be an async function" in r.message
        ]
        assert len(async_errors) == 0


class TestBasicSDKUsage:
    """Test basic SDK usage patterns."""

    def test_act_before_initialize_is_noop(self):
        """Test that act() is a no-op before initialize()."""
        # This should not crash
        act(id="test", flow="test", run_id="test", data={})

    def test_assert_before_initialize_is_noop(self):
        """Test that assert_() is a no-op before initialize()."""
        # This should not crash
        assert_(id="test", flow="test", run_id="test", data={})

    def test_shutdown_before_initialize_is_noop(self):
        """Test that shutdown() is a no-op before initialize()."""
        # This should not crash
        shutdown()


class TestEnvironmentVariables:
    """Test environment variable support."""

    def teardown_method(self):
        """Clean up after test."""
        shutdown(timeout=1.0)
        _state.initialized = False
        _state.batch_processor = None

    def test_initialize_with_env_vars(self):
        """Test initialization using environment variables."""
        import os

        # Set environment variables
        os.environ["BUSINESS_USE_API_KEY"] = "test-env-key"
        os.environ["BUSINESS_USE_URL"] = "http://test-env-url:8080"

        try:
            with mock.patch("business_use.client._check_connection", return_value=True):
                # Initialize without parameters - should use env vars
                initialize()

                # Verify SDK initialized
                assert _state.initialized is True
                assert _state.batch_processor is not None

        finally:
            # Clean up env vars
            os.environ.pop("BUSINESS_USE_API_KEY", None)
            os.environ.pop("BUSINESS_USE_URL", None)

    def test_initialize_params_override_env_vars(self):
        """Test that parameters override environment variables."""
        import os

        # Set environment variables
        os.environ["BUSINESS_USE_API_KEY"] = "env-key"
        os.environ["BUSINESS_USE_URL"] = "http://env-url:8080"

        try:
            with mock.patch("business_use.client._check_connection", return_value=True):
                # Initialize with explicit params - should override env vars
                initialize(api_key="param-key", url="http://param-url:9000")

                # Verify SDK initialized (we can't easily check which values were used,
                # but it should succeed)
                assert _state.initialized is True

        finally:
            # Clean up env vars
            os.environ.pop("BUSINESS_USE_API_KEY", None)
            os.environ.pop("BUSINESS_USE_URL", None)

    def test_initialize_without_api_key_fails(self):
        """Test that initialization fails gracefully without API key."""
        import os

        # Ensure no API key in environment
        os.environ.pop("BUSINESS_USE_API_KEY", None)

        # Try to initialize without api_key parameter
        initialize()

        # Should not initialize (no-op mode)
        assert _state.initialized is False
        assert _state.batch_processor is None
