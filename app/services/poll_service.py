"""Fetches polls from a VK conversation within a date range."""
import logging
from datetime import datetime

from app.models.poll import Poll, PollAnswer
from app.vk.client import VKAccessError, VKClient
from app.vk.methods import get_history, get_poll_by_id

logger = logging.getLogger(__name__)


async def fetch_polls(
    client: VKClient,
    peer_id: int,
    date_from: datetime,
    date_to: datetime,
) -> list[Poll]:
    """Return all polls posted in *peer_id* between *date_from* and *date_to*."""
    polls: list[Poll] = []
    offset = 0
    batch = 200
    stop = False

    logger.info("Fetching messages from peer_id=%d", peer_id)

    while not stop:
        data = await get_history(client, peer_id, offset=offset, count=batch)
        items: list[dict] = data.get("items", [])

        if not items:
            break

        for msg in items:
            msg_ts = datetime.fromtimestamp(msg["date"])

            if msg_ts > date_to:
                # Messages come newest-first by default, but we use rev=0 which
                # is newest-first. Skip messages newer than date_to.
                continue

            if msg_ts < date_from:
                # All remaining messages are older — stop.
                stop = True
                break

            for att in msg.get("attachments", []):
                if att.get("type") != "poll":
                    continue

                raw_poll = att["poll"]
                poll_id = raw_poll["id"]
                owner_id = raw_poll["owner_id"]

                logger.debug("Found poll %d (owner %d) on %s", poll_id, owner_id, msg_ts.date())

                # Fetch full poll structure to get answer list
                try:
                    full = await get_poll_by_id(client, owner_id, poll_id)
                    answers = [
                        PollAnswer(id=a["id"], text=a["text"], votes=a["votes"])
                        for a in full.get("answers", [])
                    ]
                    polls.append(
                        Poll(
                            poll_id=poll_id,
                            owner_id=owner_id,
                            question=full.get("question", ""),
                            date=msg_ts,
                            answers=answers,
                        )
                    )
                except VKAccessError:
                    logger.warning(
                        "Нет доступа к опросу %d от %s — все участники будут помечены н/д",
                        poll_id, msg_ts.date(),
                    )
                    polls.append(
                        Poll(
                            poll_id=poll_id,
                            owner_id=owner_id,
                            question="",
                            date=msg_ts,
                            inaccessible=True,
                        )
                    )

        offset += len(items)
        if len(items) < batch:
            break

    logger.info("Total polls found: %d", len(polls))
    return polls
