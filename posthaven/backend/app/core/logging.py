import logging
import sys


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stdout,
    )
    # Quiet noisy loggers
    for name in ("uvicorn.access", "uvicorn.error", "asyncio", "aioimaplib"):
        logging.getLogger(name).setLevel(logging.WARNING)


logger = logging.getLogger("posthaven")
