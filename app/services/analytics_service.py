"""Aggregates records into per-user statistics."""
from collections import defaultdict

from app.models.record import Record, VoteStatus
from app.models.user import User


def build_summary(
    records: list[Record],
    members: dict[int, User],
) -> list[dict]:
    """Return list of dicts with per-user attendance stats."""
    counts: dict[int, dict[str, int]] = defaultdict(
        lambda: {"attended": 0, "missed": 0, "org": 0, "unknown": 0, "na": 0}
    )

    for rec in records:
        if rec.status == VoteStatus.YES:
            counts[rec.user_id]["attended"] += 1
        elif rec.status == VoteStatus.NO:
            counts[rec.user_id]["missed"] += 1
        elif rec.status == VoteStatus.ORG:
            counts[rec.user_id]["org"] += 1
        elif rec.status == VoteStatus.NA:
            counts[rec.user_id]["na"] += 1
        else:
            counts[rec.user_id]["unknown"] += 1

    rows = []
    for uid, user in members.items():
        c = counts[uid]
        total = c["attended"] + c["missed"] + c["org"] + c["unknown"] + c["na"]
        rows.append(
            {
                "user": user.full_name,
                "attended": c["attended"],
                "missed": c["missed"],
                "org": c["org"],
                "unknown": c["unknown"],
                "na": c["na"],
                "total": total,
            }
        )
    return rows
