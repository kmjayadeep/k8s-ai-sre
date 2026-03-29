import os
import sys

from agents import set_tracing_disabled
from app.http import run_server

set_tracing_disabled(True)


def _get_port() -> int:
    if len(sys.argv) >= 2:
        return int(sys.argv[1])
    return int(os.getenv("PORT", "8080"))


if __name__ == "__main__":
    run_server(_get_port())
