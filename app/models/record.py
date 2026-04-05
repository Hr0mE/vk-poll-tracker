from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class VoteStatus(str, Enum):
    YES = "+"
    NO = "-"
    ORG = "орг"
    UNKNOWN = "/"
    NA = "н/д"



@dataclass
class Record:
    user_id: int
    poll_date: datetime
    status: VoteStatus
