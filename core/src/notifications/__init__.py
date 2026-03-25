"""Notifications module — dispatches flow evaluation alerts to configured channels."""

from src.config import NOTIFY_THROTTLE_SECONDS, SLACK_WEBHOOK_URL
from src.notifications.dispatcher import NotificationDispatcher


def build_dispatcher() -> NotificationDispatcher:
    """Build a NotificationDispatcher with configured notifiers.

    Reads config constants and registers any notifiers whose credentials
    are present. Returns a ready-to-use dispatcher.
    """
    dispatcher = NotificationDispatcher(throttle_seconds=NOTIFY_THROTTLE_SECONDS)

    if SLACK_WEBHOOK_URL:
        from src.notifications.slack import SlackNotifier

        dispatcher.register(SlackNotifier(SLACK_WEBHOOK_URL))

    return dispatcher
