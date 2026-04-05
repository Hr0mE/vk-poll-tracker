"""CLI entry point."""
import argparse
import asyncio
import logging
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.exporters.excel_exporter import export
from app.services.analytics_service import build_summary
from app.services.poll_service import fetch_polls
from app.services.user_service import fetch_members, fetch_votes_for_poll
from app.vk.client import VKClient
from app.vk.rate_limiter import RateLimiter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export VK poll attendance to Excel"
    )
    parser.add_argument(
        "--date-from",
        required=True,
        type=lambda s: datetime.strptime(s, "%Y-%m-%d"),
        metavar="YYYY-MM-DD",
        help="Start date (inclusive)",
    )
    parser.add_argument(
        "--date-to",
        required=True,
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59
        ),
        metavar="YYYY-MM-DD",
        help="End date (inclusive)",
    )
    parser.add_argument(
        "--output",
        default="report.xlsx",
        metavar="FILE",
        help="Output Excel file (default: report.xlsx)",
    )
    return parser.parse_args()


async def run(date_from: datetime, date_to: datetime, output: Path) -> None:
    limiter = RateLimiter(
        rate_per_sec=settings.rate_limit_per_sec,
        max_concurrent=settings.max_concurrent_requests,
    )

    async with VKClient(settings.vk_token, settings.vk_api_version, limiter) as client:
        logger.info("Step 1/4  Fetching conversation members...")
        members = await fetch_members(client, settings.peer_id)

        logger.info("Step 2/4  Fetching polls from %s to %s...", date_from.date(), date_to.date())
        polls = await fetch_polls(client, settings.peer_id, date_from, date_to)

        if not polls:
            logger.warning("No polls found in the given date range. Exiting.")
            return

        logger.info("Step 3/4  Fetching votes for %d poll(s)...", len(polls))
        all_records = []
        for poll in polls:
            records = await fetch_votes_for_poll(client, poll, members)
            all_records.extend(records)

        logger.info("Step 4/4  Building summary and exporting...")
        summary = build_summary(all_records, members)
        export(all_records, members, summary, output)

    logger.info("Done.")


def main() -> None:
    args = parse_args()
    asyncio.run(run(args.date_from, args.date_to, Path(args.output)))


if __name__ == "__main__":
    main()
