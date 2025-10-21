import logging

from src.events.models import NewEvent

log = logging.getLogger(__name__)


async def handle_new_event(ev: NewEvent) -> bool:
    log.info(f"Handling new event: {ev.ev_id}")
    return True
