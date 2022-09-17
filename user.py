import db
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
    db: Any

    def load(self) -> bool:
        select_stmt = f'''
            SELECT id, given_name, family_name, full_name, primary_email, picture
                FROM user
                WHERE id = {self.id}
        '''
        result = db.execute_read(self.db, select_stmt)
        if result is not None:
            row = result[0] # should only be one
            self.id = row['id']
            self.given_name = row['given_name']
            self.family_name = row['family_name']
            self.full_name = row['full_name']
            self.primary_email = row['primary_email']
            self.picture = row['picture']
            return True
        else:
            return False

    def save(self):
        insert_stmt = f'''
            INSERT INTO user (id, given_name, family_name, full_name, primary_email, picture)
                VALUES ({self.id}, "{self.given_name}", "{self.family_name}", "{self.full_name}", "{self.primary_email}", "{self.picture}");
        '''
        db.execute_write(self.db, insert_stmt)

    def __init__(self, **data):
        super().__init__(**data)
        if not self.load():
            self.save()



