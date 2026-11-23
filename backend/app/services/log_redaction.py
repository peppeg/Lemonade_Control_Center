"""Keep the LCC key out of the server log.

Browsers cannot add headers to WebSocket connections, so the frontend sends the
key as `lcc_key` in the URL, and Uvicorn logs the full URL of every connection.
"""
from __future__ import annotations

import logging
import re

# The loggers Uvicorn writes request URLs to: HTTP and WebSocket respectively.
URL_LOGGERS = ("uvicorn.access", "uvicorn.error")

_KEY_PARAMETER = re.compile(r"([?&]lcc_key=)[^&\s]*")


def _redact(value: object) -> object:
    if isinstance(value, str):
        return _KEY_PARAMETER.sub(r"\1<redacted>", value)
    return value


class KeyRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _redact(record.msg)
        # Uvicorn's access formatter unpacks the tuple, so its shape must stay.
        if isinstance(record.args, tuple):
            record.args = tuple(_redact(arg) for arg in record.args)
        return True


_filter = KeyRedactionFilter()


def redact_key_in_logs() -> None:
    """Install the filter; calling it again has no effect."""
    for name in URL_LOGGERS:
        logging.getLogger(name).addFilter(_filter)
