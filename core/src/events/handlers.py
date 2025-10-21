import logging

from bubus import EventBus

from src.events.models import NewBatchEvent, NewEvent

log = logging.getLogger(__name__)


def new_bus():
    bus = EventBus()

    bus.on(NewBatchEvent, handle_new_batch_event)
    bus.on(NewEvent, handle_new_event)

    return bus


async def handle_new_batch_event(ev: NewBatchEvent) -> None:
    for ev_id in ev.ev_ids:
        ev.event_bus.dispatch(NewEvent(ev_id=ev_id))


async def handle_new_event(ev: NewEvent) -> None:
    log.info(f"Handling new event: {ev.ev_id}")
