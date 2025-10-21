from bubus import BaseEvent


class NewEvent(BaseEvent[bool]):
    ev_id: str
