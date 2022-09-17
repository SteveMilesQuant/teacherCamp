from enum import Enum
from pydantic import BaseModel
from typing import List, Optional, Any


class Role(Enum):
    GUARDIAN = 0
    INSTRUCTOR = 1
    ADMIN = 2


class User(BaseModel):
    id: int
    given_name: str
    family_name: str
    full_name: str
    primary_email: str
    picture: str
    other_emails: Optional[List[str]] = []
    roles: Optional[List[bool]] = [False] * len(Role)





