"""Integration tests for the notifications module factory (build_dispatcher / get_dispatcher)."""

import pytest

import src.notifications
from src.notifications import build_dispatcher, get_dispatcher
from src.notifications.dispatcher import NotificationDispatcher


@pytest.fixture(autouse=True)
def _reset_dispatcher() -> None:  # type: ignore[misc]
    """Reset the module-level _dispatcher singleton before each test."""
    src.notifications._dispatcher = None
    yield  # type: ignore[misc]
    src.notifications._dispatcher = None


class TestBuildDispatcher:
    """Tests for build_dispatcher() with various config values."""

    def test_no_config_returns_empty_dispatcher(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With no webhook/DSN configured, dispatcher has zero notifiers."""
        monkeypatch.setattr(src.notifications, "SLACK_WEBHOOK_URL", None)
        monkeypatch.setattr(src.notifications, "SENTRY_DSN", None)
        monkeypatch.setattr(src.notifications, "NOTIFY_THROTTLE_SECONDS", 0)

        dispatcher = build_dispatcher()

        assert isinstance(dispatcher, NotificationDispatcher)
        assert len(dispatcher.notifiers) == 0

    def test_slack_configured_adds_one_notifier(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With SLACK_WEBHOOK_URL set, dispatcher has exactly one notifier."""
        monkeypatch.setattr(
            src.notifications,
            "SLACK_WEBHOOK_URL",
            "https://hooks.slack.com/services/test",
        )
        monkeypatch.setattr(src.notifications, "SENTRY_DSN", None)
        monkeypatch.setattr(src.notifications, "NOTIFY_THROTTLE_SECONDS", 0)

        dispatcher = build_dispatcher()

        assert len(dispatcher.notifiers) == 1
        from src.notifications.slack import SlackNotifier

        assert isinstance(dispatcher.notifiers[0], SlackNotifier)

    def test_sentry_configured_adds_one_notifier(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With SENTRY_DSN set, dispatcher has exactly one notifier."""
        monkeypatch.setattr(src.notifications, "SLACK_WEBHOOK_URL", None)
        monkeypatch.setattr(
            src.notifications,
            "SENTRY_DSN",
            "https://abc@sentry.io/123",
        )
        monkeypatch.setattr(src.notifications, "NOTIFY_THROTTLE_SECONDS", 0)

        dispatcher = build_dispatcher()

        assert len(dispatcher.notifiers) == 1
        from src.notifications.sentry import SentryNotifier

        assert isinstance(dispatcher.notifiers[0], SentryNotifier)

    def test_both_configured_adds_two_notifiers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With both SLACK_WEBHOOK_URL and SENTRY_DSN, dispatcher has two notifiers."""
        monkeypatch.setattr(
            src.notifications,
            "SLACK_WEBHOOK_URL",
            "https://hooks.slack.com/services/test",
        )
        monkeypatch.setattr(
            src.notifications,
            "SENTRY_DSN",
            "https://abc@sentry.io/123",
        )
        monkeypatch.setattr(src.notifications, "NOTIFY_THROTTLE_SECONDS", 0)

        dispatcher = build_dispatcher()

        assert len(dispatcher.notifiers) == 2

        from src.notifications.sentry import SentryNotifier
        from src.notifications.slack import SlackNotifier

        types = {type(n) for n in dispatcher.notifiers}
        assert types == {SlackNotifier, SentryNotifier}

    def test_throttle_seconds_forwarded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """NOTIFY_THROTTLE_SECONDS is passed to the dispatcher constructor."""
        monkeypatch.setattr(src.notifications, "SLACK_WEBHOOK_URL", None)
        monkeypatch.setattr(src.notifications, "SENTRY_DSN", None)
        monkeypatch.setattr(src.notifications, "NOTIFY_THROTTLE_SECONDS", 42)

        dispatcher = build_dispatcher()

        assert dispatcher._throttle_seconds == 42


class TestGetDispatcher:
    """Tests for get_dispatcher() singleton access."""

    def test_before_build_returns_noop_dispatcher(self) -> None:
        """Before build_dispatcher() is called, get_dispatcher() returns an empty dispatcher."""
        dispatcher = get_dispatcher()

        assert isinstance(dispatcher, NotificationDispatcher)
        assert len(dispatcher.notifiers) == 0

    def test_after_build_returns_same_instance(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """After build_dispatcher(), get_dispatcher() returns the built instance."""
        monkeypatch.setattr(src.notifications, "SLACK_WEBHOOK_URL", None)
        monkeypatch.setattr(src.notifications, "SENTRY_DSN", None)
        monkeypatch.setattr(src.notifications, "NOTIFY_THROTTLE_SECONDS", 0)

        built = build_dispatcher()
        got = get_dispatcher()

        assert got is built

    def test_noop_dispatcher_is_fresh_each_call(self) -> None:
        """When _dispatcher is None, each get_dispatcher() call returns a new instance."""
        d1 = get_dispatcher()
        d2 = get_dispatcher()

        # They are separate instances (not cached)
        assert d1 is not d2
