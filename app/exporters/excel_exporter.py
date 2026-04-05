"""Exports records and summary to an Excel file."""
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from app.models.record import Record, VoteStatus
from app.models.user import User

logger = logging.getLogger(__name__)


def export(
    records: list[Record],
    members: dict[int, User],
    summary: list[dict],
    output_path: Path,
) -> None:
    # ---- Sheet 1: matrix (user x date) ----
    dates = sorted({r.poll_date.date() for r in records})
    date_labels = [d.strftime("%d.%m") for d in dates]

    matrix_rows = []
    for uid, user in members.items():
        row: dict = {"user": user.full_name}
        user_records = {r.poll_date.date(): r.status for r in records if r.user_id == uid}
        for d in dates:
            status = user_records.get(d, VoteStatus.UNKNOWN)
            row[d.strftime("%d.%m")] = status.value
        matrix_rows.append(row)

    df_matrix = pd.DataFrame(matrix_rows)

    # ---- Micro-stats rows at the bottom of matrix ----
    stat_labels = [
        (VoteStatus.YES, "Придут"),
        (VoteStatus.NO, "Не придут"),
        (VoteStatus.UNKNOWN, "Не ответили"),
        (VoteStatus.ORG, "Организаторы"),
        (VoteStatus.NA, "Нет данных"),
    ]
    for vote_status, label in stat_labels:
        stat_row: dict = {"user": label}
        for d in dates:
            col = d.strftime("%d.%m")
            stat_row[col] = sum(
                1 for r in records
                if r.poll_date.date() == d and r.status == vote_status
            )
        matrix_rows.append(stat_row)

    df_matrix = pd.DataFrame(matrix_rows).rename(columns={"user": "Участник"})

    # ---- Sheet 2: summary ----
    df_summary = pd.DataFrame(summary).rename(columns={
        "user": "Участник",
        "attended": "Был",
        "missed": "Не был",
        "org": "Организатор",
        "unknown": "Не ответил",
        "na": "Нет данных",
        "total": "Всего",
    })

    # ---- Write Excel ----
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_matrix.to_excel(writer, sheet_name="Матрица", index=False)
        df_summary.to_excel(writer, sheet_name="Сводка", index=False)

    logger.info("Report saved to %s", output_path)
