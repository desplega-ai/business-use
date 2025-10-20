import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from enum import Enum
from functools import wraps
from typing import Any, TypeVar

from sqlalchemy import text
from sqlalchemy.exc import (
    DisconnectionError,
    IntegrityError,
    OperationalError,
)
from sqlalchemy.exc import (
    TimeoutError as SQLTimeoutError,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.async_db import AsyncSessionLocal

TRANSACTION_VAR: ContextVar[AsyncSession | None] = ContextVar(
    "__dbapi_transaction", default=None
)

PARALLEL_TRANSACTION_VAR: ContextVar[AsyncSession | None] = ContextVar(
    "__dbapi_parallel_transaction", default=None
)

DEFAULT_TIMEOUT = 180

DEFAULT_RETRIES = 5
DEFAULT_BASE_DELAY = 1.0  # seconds

# Common transient database errors that can be retried
RETRYABLE_EXCEPTIONS = (
    DisconnectionError,
    OperationalError,
    SQLTimeoutError,
    IntegrityError,
    ConnectionError,
    asyncio.TimeoutError,
)


class IsolationLevel(Enum):
    READ_UNCOMMITTED = "READ UNCOMMITTED"
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"
    SERIALIZABLE = "SERIALIZABLE"


@asynccontextmanager  # noqa
async def transactional(
    *,
    isolation_level: IsolationLevel | None = None,
    nested: bool = False,
    force_new: bool = False,
    parallel_transaction: bool = False,
    dry_run: bool = False,
    log: bool = False,
) -> Any:
    if parallel_transaction:
        session_transaction_global_var = PARALLEL_TRANSACTION_VAR
    else:
        session_transaction_global_var = TRANSACTION_VAR

    session = session_transaction_global_var.get()

    if not session or force_new:
        async with AsyncSessionLocal() as session, session.begin():
            tok = session_transaction_global_var.set(session)

            try:
                async with asyncio.timeout(DEFAULT_TIMEOUT):
                    if isolation_level:
                        if hasattr(session, "__isolation_level"):
                            current_isolation_level = getattr(
                                session, "__isolation_level"
                            )

                            if current_isolation_level != isolation_level:
                                logging.warning(
                                    f"Changing isolation level from {current_isolation_level} to {isolation_level}"
                                )

                        # SQLite only supports READ UNCOMMITTED and SERIALIZABLE
                        # READ UNCOMMITTED via PRAGMA read_uncommitted = 1
                        # SERIALIZABLE is default (PRAGMA read_uncommitted = 0)
                        # Other levels (READ COMMITTED, REPEATABLE READ) are not supported
                        if isolation_level == IsolationLevel.READ_UNCOMMITTED:
                            await session.execute(text("PRAGMA read_uncommitted = 1"))
                        elif isolation_level == IsolationLevel.SERIALIZABLE:
                            await session.execute(text("PRAGMA read_uncommitted = 0"))
                        else:
                            logging.warning(
                                f"SQLite does not support {isolation_level.value}, using SERIALIZABLE instead"
                            )
                            await session.execute(text("PRAGMA read_uncommitted = 0"))

                        setattr(session, "__isolation_level", isolation_level)

                    if log:
                        logging.info(
                            f"Transaction started with isolation level: {isolation_level}"
                        )

                    yield session

            except TimeoutError:
                logging.error(
                    f"Transaction timed out after {DEFAULT_TIMEOUT} seconds!!!1"
                )

                raise

            finally:
                if dry_run:
                    logging.info("Rolling back transaction due to dry run")
                    await session.rollback()

                session_transaction_global_var.reset(tok)

    elif nested:
        async with session.begin_nested():
            if log:
                logging.info(
                    f"Nested transaction started with isolation level: {isolation_level}"
                )

            yield session

    else:
        if log:
            logging.info("Reusing existing transaction")

        yield session


_T = TypeVar("_T")


def with_retries(
    max_tries: int = DEFAULT_RETRIES,
    exceptions: tuple[type[Exception], ...] = RETRYABLE_EXCEPTIONS,
    base_delay: float = DEFAULT_BASE_DELAY,
) -> Callable[[Callable[..., Awaitable[_T]]], Callable[..., Awaitable[_T]]]:
    def decorator(
        func: Callable[..., Awaitable[_T]],
    ) -> Callable[..., Awaitable[_T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_tries):
                getattr(logging, "info" if attempt == 0 else "warning")(
                    f"Function {func.__name__} attempt {attempt + 1} of {max_tries}"
                )

                try:
                    return await func(*args, **kwargs)

                except exceptions as e:
                    last_exception = e

                    if attempt < max_tries - 1:
                        delay = base_delay * (2**attempt)

                        logging.warning(
                            f"Function {func.__name__} attempt {attempt + 1} failed, retrying in {delay}s: {e}"
                        )

                        await asyncio.sleep(delay)

                    else:
                        logging.error(
                            f"Function {func.__name__} failed after {max_tries} attempts: {e}"
                        )

            # If we get here, all retries failed
            if last_exception:
                raise last_exception

        return wrapper

    return decorator
