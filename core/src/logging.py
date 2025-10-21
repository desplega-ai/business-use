import logging

from src.config import LOG_LEVEL
from src.models import CoreEnum

LOG_FORMAT_DEBUG = "%(levelname)s:%(message)s:%(pathname)s:%(funcName)s:%(lineno)d"
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] %(module)s - %(message)s"

DATE_FORMAT = "%Y-%m-%d %H:%M:%S %z"


class LogLevels(CoreEnum):
    info = "INFO"
    warn = "WARN"
    error = "ERROR"
    debug = "DEBUG"


def configure_logging() -> None:
    log_level = str(LOG_LEVEL).upper()  # cast to string
    log_levels = list(LogLevels)

    if log_level not in log_levels:
        # we use error as the default log level
        logging.basicConfig(
            level=LogLevels.error, format=LOG_FORMAT, datefmt=DATE_FORMAT
        )
        return

    if log_level == LogLevels.debug:
        logging.basicConfig(
            level=log_level, format=LOG_FORMAT_DEBUG, datefmt=DATE_FORMAT
        )
        return

    logging.basicConfig(level=log_level, format=LOG_FORMAT, datefmt=DATE_FORMAT)
