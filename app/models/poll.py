from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PollAnswer:
    id: int
    text: str
    votes: int


@dataclass
class Poll:
    poll_id: int
    owner_id: int
    question: str
    date: datetime
    answers: list[PollAnswer] = field(default_factory=list)
    inaccessible: bool = False
