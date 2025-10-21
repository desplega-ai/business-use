import logging
from uuid import uuid4

from bubus import EventBus
from sqlmodel import select

from src.db.transactional import transactional
from src.events.models import NewBatchEvent, NewEvent
from src.models import EvalOutput, Event
from src.utils.time import now

log = logging.getLogger(__name__)


def new_bus():
    bus = EventBus()

    bus.on(NewBatchEvent, handle_new_batch_event)
    bus.on(NewEvent, handle_new_event)

    return bus


async def handle_new_batch_event(ev: NewBatchEvent) -> None:
    """Handle new batch of events - dispatch individual events and run evaluations."""
    # Dispatch individual event handlers
    for ev_id in ev.ev_ids:
        ev.event_bus.dispatch(NewEvent(ev_id=ev_id))

    # Fetch events to get run_id and flow information
    async with transactional() as session:
        stmt = select(Event).where(Event.id.in_(ev.ev_ids))  # type: ignore
        result = await session.execute(stmt)
        events = result.scalars().all()

        if not events:
            log.warning("No events found for batch evaluation")
            return

        # Group events by (run_id, flow)
        runs_by_flow: dict[tuple[str, str], list[Event]] = {}
        for event in events:
            key = (event.run_id, event.flow)
            if key not in runs_by_flow:
                runs_by_flow[key] = []
            runs_by_flow[key].append(event)

        # Run evaluation for each unique (run_id, flow) pair
        for (run_id, flow), flow_events in runs_by_flow.items():
            log.info(
                f"Running evaluation for run_id={run_id}, flow={flow} "
                f"({len(flow_events)} events)"
            )

            try:
                from src.eval import eval_flow_run

                eval_result = await eval_flow_run(run_id=run_id, flow=flow)

                # Store evaluation result
                eval_output = EvalOutput(
                    id=str(uuid4()),
                    flow=flow,
                    run_id=run_id,
                    trigger_ev_id=flow_events[0].id if flow_events else None,
                    output=eval_result,
                    created_at=now(),
                    status="active",
                )

                session.add(eval_output)
                await session.commit()

                log.info(
                    f"Evaluation completed for run_id={run_id}, flow={flow}: "
                    f"status={eval_result.status}"
                )

            except Exception as e:
                log.exception(f"Failed to evaluate run_id={run_id}, flow={flow}: {e}")
                # Don't fail the entire batch if one evaluation fails
                continue


async def handle_new_event(ev: NewEvent) -> None:
    log.info(f"Handling new event: {ev.ev_id}")
