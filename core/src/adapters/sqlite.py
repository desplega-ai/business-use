"""SQLite storage adapter for events and nodes.

This module encapsulates all SQLite-specific queries, making it easy to
swap out for a different storage backend at desplega.ai.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import asc, select

from src.models import Event, Node


class SqliteEventStorage:
    """SQLite adapter for fetching events and nodes.

    This class encapsulates all database operations, making the core
    domain logic independent of the storage layer.
    """

    async def get_event_by_id(
        self,
        event_id: str,
        session: AsyncSession,
    ) -> Event | None:
        """Fetch a single event by ID.

        Args:
            event_id: Event identifier
            session: Database session

        Returns:
            Event if found, None otherwise
        """
        result = await session.execute(select(Event).where(Event.id == event_id))
        return result.scalar_one_or_none()

    async def get_events_by_run(
        self,
        run_id: str,
        flow: str,
        session: AsyncSession,
    ) -> list[Event]:
        """Fetch all events for a specific run_id + flow tuple.

        This is the NEW method that replaces time-window heuristics.
        It directly queries by run_id and flow, which are now part of
        the Event model.

        Args:
            run_id: Run identifier
            flow: Flow identifier
            session: Database session

        Returns:
            List of events, ordered by timestamp (oldest first)
        """
        result = await session.execute(
            select(Event)
            .where(
                Event.run_id == run_id,
                Event.flow == flow,
            )
            .order_by(asc(Event.ts))
        )
        return list(result.scalars().all())

    async def get_nodes_by_flow(
        self,
        flow: str,
        session: AsyncSession,
    ) -> list[Node]:
        """Fetch all node definitions for a flow.

        Args:
            flow: Flow identifier
            session: Database session

        Returns:
            List of active (non-deleted) nodes for the flow
        """
        result = await session.execute(
            select(Node).where(
                Node.flow == flow,
                Node.deleted_at.is_(None),  # type: ignore
            )
        )
        return list(result.scalars().all())

    async def get_all_nodes(
        self,
        session: AsyncSession,
    ) -> list[Node]:
        """Fetch all active node definitions.

        Args:
            session: Database session

        Returns:
            List of all active (non-deleted) nodes
        """
        result = await session.execute(
            select(Node).where(
                Node.deleted_at.is_(None),  # type: ignore
            )
        )
        return list(result.scalars().all())
