import json
import logging
import sys
from datetime import UTC, datetime

ERROR = logging.ERROR
INFO = logging.INFO
WARNING = logging.WARNING

_logger = logging.getLogger("txtlocal")


class JsonLines(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line: dict[str, object] = {
            "event": record.getMessage(),
            "level": record.levelname.lower(),
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            line.update(fields)
        return json.dumps(line, default=str, separators=(",", ":"))


def configure() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLines())

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)


def log(event: str, *, level: int = logging.INFO, **fields: object) -> None:
    _logger.log(level, event, extra={"fields": fields})
