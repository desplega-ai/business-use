from bubus import BaseEvent


class NewBatchEvent(BaseEvent[None]):
    ev_ids: list[str]


class NewEvent(BaseEvent[None]):
    ev_id: str
