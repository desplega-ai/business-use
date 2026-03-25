"""Notifications module — dispatches flow evaluation alerts to configured channels."""

from src.config import NOTIFY_THROTTLE_SECONDS
from src.notifications.dispatcher import NotificationDispatcher


def build_dispatcher() -> NotificationDispatcher:
    """Build a NotificationDispatcher with configured notifiers.

    Reads config constants and registers any notifiers whose credentials
    are present. Returns a ready-to-use dispatcher.
    """
    dispatcher = NotificationDispatcher(throttle_seconds=NOTIFY_THROTTLE_SECONDS)
    # Notifiers registered in subsequent phases
    return dispatcher
