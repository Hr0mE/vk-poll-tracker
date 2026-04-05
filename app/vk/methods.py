"""Typed wrappers around VK API methods."""
from typing import Any

from app.vk.client import VKClient


async def get_history(
    client: VKClient,
    peer_id: int,
    offset: int = 0,
    count: int = 200,
) -> dict[str, Any]:
    return await client.call(
        "messages.getHistory",
        peer_id=peer_id,
        offset=offset,
        count=count,
        rev=0,
    )


async def get_poll_by_id(
    client: VKClient,
    owner_id: int,
    poll_id: int,
) -> dict[str, Any]:
    return await client.call(
        "polls.getById",
        owner_id=owner_id,
        poll_id=poll_id,
        is_board=0,
    )


async def get_voters(
    client: VKClient,
    owner_id: int,
    poll_id: int,
    answer_ids: list[int],
    count: int = 1000,
) -> list[dict[str, Any]]:
    return await client.call(
        "polls.getVoters",
        owner_id=owner_id,
        poll_id=poll_id,
        answer_ids=",".join(str(a) for a in answer_ids),
        count=count,
        is_board=0,
    )


async def get_conversation_members(
    client: VKClient,
    peer_id: int,
) -> dict[str, Any]:
    return await client.call(
        "messages.getConversationMembers",
        peer_id=peer_id,
    )
