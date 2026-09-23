import os

import uvicorn

from txtlocal.entrypoints.api import app
from txtlocal.shared import runtime

LOOPBACK = "127.0.0.1"
DEFAULT_PORT = 9000


def main() -> None:
    config = uvicorn.Config(
        app,
        host=os.environ.get("HOST", LOOPBACK),
        log_level="warning",
        port=int(os.environ.get("PORT", DEFAULT_PORT)),
    )
    runtime.run(uvicorn.Server(config).serve())


if __name__ == "__main__":
    main()
