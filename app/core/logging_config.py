import logging

from app.core.middleware import request_id_var

_FORMAT = "%(asctime)s %(levelname)s [%(name)s] [req=%(request_id)s] %(message)s"


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging(level: str) -> None:
    """Sem isto o Uvicorn descarta os logs INFO do logger "studybuddy"."""
    logger = logging.getLogger("studybuddy")
    logger.setLevel(level)
    if any(isinstance(handler_filter, RequestIdFilter) for handler in logger.handlers for handler_filter in handler.filters):
        return
    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(logging.Formatter(_FORMAT))
    logger.addHandler(handler)
