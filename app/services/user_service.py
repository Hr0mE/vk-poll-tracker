"""Fetches conversation members and poll voters."""
import logging
from typing import Any

from app.models.poll import Poll
from app.models.record import Record, VoteStatus
from app.models.user import User
from app.keywords import load_keywords
from app.vk.client import VKAccessError, VKClient
from app.vk.methods import get_conversation_members, get_voters

logger = logging.getLogger(__name__)


def _classify_answer(
    text: str,
    yes_words: list[str],
    no_words: list[str],
    org_words: list[str],
) -> VoteStatus | None:
    lower = text.lower()
    status = None
    if any(w in lower for w in yes_words):
        status = VoteStatus.YES
    if any(w in lower for w in no_words):
        status = VoteStatus.NO
    if any(w in lower for w in org_words):
        status = VoteStatus.ORG
    return status


async def fetch_members(client: VKClient, peer_id: int) -> dict[int, User]:
    """Return {user_id: User} for all conversation members."""
    data = await get_conversation_members(client, peer_id)
    profiles: list[dict[str, Any]] = data.get("profiles", [])
    members: dict[int, User] = {}
    for p in profiles:
        uid = p["id"]
        members[uid] = User(
            user_id=uid,
            first_name=p.get("first_name", ""),
            last_name=p.get("last_name", ""),
        )
    logger.info("Conversation members: %d", len(members))
    return members


async def fetch_votes_for_poll(
    client: VKClient,
    poll: Poll,
    members: dict[int, User],
) -> list[Record]:
    """Return a Record for every member for the given poll."""
    if poll.inaccessible:
        return [Record(user_id=uid, poll_date=poll.date, status=VoteStatus.NA) for uid in members]

    kw = load_keywords()

    # Classify answers into YES / NO / ORG buckets
    yes_ids: list[int] = []
    no_ids: list[int] = []
    org_ids: list[int] = []
    for answer in poll.answers:
        s = _classify_answer(answer.text, kw["yes"], kw["no"], kw["org"])
        if s == VoteStatus.YES:
            yes_ids.append(answer.id)
        elif s == VoteStatus.NO:
            no_ids.append(answer.id)
        elif s == VoteStatus.ORG:
            org_ids.append(answer.id)

    voted_yes: set[int] = set()
    voted_no: set[int] = set()
    voted_org: set[int] = set()

    try:
        if yes_ids:
            rows = await get_voters(client, poll.owner_id, poll.poll_id, yes_ids)
            for row in rows:
                for uid in row.get("users", {}).get("items", []):
                    voted_yes.add(uid)

        if no_ids:
            rows = await get_voters(client, poll.owner_id, poll.poll_id, no_ids)
            for row in rows:
                for uid in row.get("users", {}).get("items", []):
                    voted_no.add(uid)

        if org_ids:
            rows = await get_voters(client, poll.owner_id, poll.poll_id, org_ids)
            for row in rows:
                for uid in row.get("users", {}).get("items", []):
                    voted_org.add(uid)
    except VKAccessError:
        logger.warning(
            "Нет доступа к голосам опроса %d от %s — все участники будут помечены н/д",
            poll.poll_id, poll.date.date(),
        )
        return [Record(user_id=uid, poll_date=poll.date, status=VoteStatus.NA) for uid in members]

    records: list[Record] = []
    for uid in members:
        if uid in voted_org:
            status = VoteStatus.ORG
        elif uid in voted_yes:
            status = VoteStatus.YES
        elif uid in voted_no:
            status = VoteStatus.NO
        else:
            status = VoteStatus.UNKNOWN
        records.append(Record(user_id=uid, poll_date=poll.date, status=status))

    return records
