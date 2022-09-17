import db
from enum import Enum
from pydantic import BaseModel
from typing import Dict, List, Optional, Any


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
    db: Any
    other_emails: Optional[List[str]] = []
    roles: Optional[List[Role]] = []
    permissible_endpoints: Optional[List[str]] = []

    def update_permissible_endpoints(self):
        where_clause = None
        for role in self.roles:
            if not where_clause:
                where_clause = f'role = "{role.name}"'
            else:
                where_clause = where_clause + f'or role = "{role.name}"'
        select_stmt = f'''
            SELECT endpoint
                FROM role_permissions
                WHERE {where_clause}
        '''
        result = db.execute_read(self.db, select_stmt)

        self.permissible_endpoints.clear()
        for row in result:
            self.permissible_endpoints.append(row['endpoint'])


    def load(self) -> bool:
        select_stmt = f'''
            SELECT given_name, family_name, full_name, primary_email, picture
                FROM user
                WHERE id = {self.id}
        '''
        result = db.execute_read(self.db, select_stmt)
        if result is None:
            return False;
        row = result[0] # should only be one
        self.given_name = row['given_name']
        self.family_name = row['family_name']
        self.full_name = row['full_name']
        self.primary_email = row['primary_email']
        self.picture = row['picture']

        select_stmt = f'''
            SELECT role
                FROM user_x_roles
                WHERE id = {self.id}
        '''
        result = db.execute_read(self.db, select_stmt)
        self.roles.clear()
        for row in result:
            role_enum = Role(row['role'])
            self.roles.append(role_enum)

        self.update_permissible_endpoints()
        return True

    def create(self):
        insert_stmt = f'''
            INSERT INTO user (id, given_name, family_name, full_name, primary_email, picture)
                VALUES ({self.id}, "{self.given_name}", "{self.family_name}", "{self.full_name}", "{self.primary_email}", "{self.picture}");
        '''
        db.execute_write(self.db, insert_stmt)

        self.roles.clear()
        self.roles.append(Role.GUARDIAN)
        insert_stmt = f'''
            INSERT INTO user_x_roles (id, role)
                VALUES ({self.id}, "{Role.GUARDIAN}");
        '''
        db.execute_write(self.db, insert_stmt)

        self.update_permissible_endpoints()

    def update(self):
        update_stmt = f'''
            UPDATE user
                SET given_name="{self.given_name}", family_name="{self.family_name}",
                    full_name="{self.full_name}", primary_email="{self.primary_email}", picture="{self.picture}"
                WHERE id = {self.id};
        '''
        db.execute_write(self.db, update_stmt)

        delete_stmt = f'''
            DELETE FROM user_x_roles WHERE id={self.id};
        '''
        db.execute_write(self.db, delete_stmt)
        for role in self.roles:
            insert_stmt = f'''
                INSERT INTO user_x_roles (id, role)
                    VALUES ({self.id}, "{role.name}");
            '''
            db.execute_write(self.db, insert_stmt)


    def __init__(self, **data):
        super().__init__(**data)
        if not self.load():
            self.create()



