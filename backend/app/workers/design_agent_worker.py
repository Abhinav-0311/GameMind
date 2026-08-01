"""Single-purpose worker process for durable design-agent jobs."""

import logging
import os
import signal
import socket
import time

from app.config import settings
from app.database import SessionLocal
from app.design_agent.jobs import DesignAgentJobService


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gamemind.design_agent_worker")
stopping = False


def _request_stop(_signum, _frame) -> None:
    global stopping
    stopping = True


def main() -> int:
    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    jobs = DesignAgentJobService(SessionLocal)
    logger.info("Design-agent worker started as %s", worker_id)
    while not stopping:
        processed = jobs.process_one(worker_id)
        if not processed:
            time.sleep(settings.DESIGN_AGENT_JOB_POLL_SECONDS)
    logger.info("Design-agent worker stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
