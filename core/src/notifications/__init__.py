"""Notifications module — dispatches flow evaluation alerts to configured channels."""

from src.config import NOTIFY_THROTTLE_SECONDS, SENTRY_DSN, SLACK_WEBHOOK_URL
from src.notifications.dispatcher import NotificationDispatcher

_dispatcher: NotificationDispatcher | None = None


def build_dispatcher() -> NotificationDispatcher:
    """Build a NotificationDispatcher with configured notifiers.

    Reads config constants and registers any notifiers whose credentials
    are present. Stores the result as a module-level singleton accessible
    via ``get_dispatcher()``.
    """
    global _dispatcher

    dispatcher = NotificationDispatcher(throttle_seconds=NOTIFY_THROTTLE_SECONDS)

    if SLACK_WEBHOOK_URL:
        from src.notifications.slack import SlackNotifier

        dispatcher.register(SlackNotifier(SLACK_WEBHOOK_URL))

    if SENTRY_DSN:
        from src.notifications.sentry import SentryNotifier

        dispatcher.register(SentryNotifier())

    _dispatcher = dispatcher
    return dispatcher


def get_dispatcher() -> NotificationDispatcher:
    """Return the singleton dispatcher, or an empty no-op dispatcher if not initialised."""
    if _dispatcher is None:
        return NotificationDispatcher()
    return _dispatcher
