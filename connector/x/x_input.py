# -*- coding: utf-8 -*-
import asyncio
import logging
import sys
import traceback

sys.path.append(".")

from conf.config import CONF
from connector.x.x_api import XAPIError
from connector.x.x_ingest import poll_mentions_once

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def input_handler():
    try:
        ingested = poll_mentions_once()
        if ingested:
            logger.info("poll ingested %s mention(s)", ingested)
    except XAPIError as exc:
        logger.error("x input api error: %s", exc)
    except Exception:
        logger.error(traceback.format_exc())


async def run_input_loop():
    poll_interval = int(CONF.get("x", {}).get("poll_interval_seconds", 300))
    while True:
        await input_handler()
        await asyncio.sleep(poll_interval)


async def main():
    await run_input_loop()


if __name__ == "__main__":
    asyncio.run(main())
