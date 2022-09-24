from db import execute_read, execute_write
from enum import Enum
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import date


class Role(BaseModel):
    name: str
    db: Any
    permissible_endpoints: Optional[Dict[str, str]] = {}

    def __init__(self, **data):
        super().__init__(**data)
        self.permissible_endpoints.clear()
        select_stmt = f'''
            SELECT endpoint, endpoint_title
                FROM role_permissions
                WHERE role = "{self.name}"
        '''
        result = execute_read(self.db, select_stmt)
        for row in result:
            self.permissible_endpoints[row['endpoint']] = row['endpoint_title']


def load_all_roles(db: Any) -> Dict[str, Role]:
    all_roles = {}
    select_stmt = f'''
        SELECT DISTINCT role
            FROM role_permissions
    '''
    result = execute_read(db, select_stmt)
    for row in result:
        role_name = row['role']
        all_roles[role_name] = Role(name=role_name, db=db)
    return all_roles


class Student(BaseModel):
    id: Optional[int] = None  # we use AUTOMATICINCREMENT on create, so this wouldn't be necessary then
    name: Optional[str] = None
    birthdate: Optional[date] = None
    school: Optional[str] = ""
    db: Any

    def load(self) -> bool:
        select_stmt = f'''
            SELECT *
                FROM student
                WHERE id = {self.id}
        '''
        result = execute_read(self.db, select_stmt)
        if result is None:
            return False;
        row = result[0] # should only be one
        self.name = row['name']
        year, month, day = row['birthdate'].split('-')
        self.birthdate = date(int(year), int(month), int(day))
        self.school = row['school']
        return True

    def create(self):
        sql_date = self.birthdate.strftime('%Y-%m-%d')
        insert_stmt = f'''
            INSERT INTO student (name, birthdate, school)
                VALUES ("{self.name}", "{sql_date}", "{self.school}");
        '''
        self.id = execute_write(self.db, insert_stmt)

    def update(self):
        sql_date = self.birthdate.strftime('%Y-%m-%d')
        update_stmt = f'''
            UPDATE student
                SET name="{self.name}", birthdate="{sql_date}",
                    school="{self.school}"
                WHERE id = {self.id};
        '''
        execute_write(self.db, update_stmt)

    def delete(self):
        delete_stmt = f'''
            DELETE FROM user_x_students
                WHERE student_id = {self.id};
        '''
        execute_write(self.db, delete_stmt)
        delete_stmt = f'''
            DELETE FROM student
                WHERE id = {self.id};
        '''
        execute_write(self.db, delete_stmt)

    def __init__(self, **data):
        super().__init__(**data)
        if self.id is None:
            self.create()
        elif not self.load():
            self.create()


class User(BaseModel):
    id: int
    given_name: str
    family_name: str
    full_name: str
    google_email: str
    picture: str
    db: Any
    roles: Optional[List[str]] = []
    student_ids: Optional[List[int]] = []

    def load(self) -> bool:
        select_stmt = f'''
            SELECT *
                FROM user
                WHERE id = {self.id}
        '''
        result = execute_read(self.db, select_stmt)
        if result is None:
            return False;
        row = result[0] # should only be one
        self.given_name = row['given_name']
        self.family_name = row['family_name']
        self.full_name = row['full_name']
        self.google_email = row['google_email']
        self.picture = row['picture']

        select_stmt = f'''
            SELECT role
                FROM user_x_roles
                WHERE user_id = {self.id}
        '''
        result = execute_read(self.db, select_stmt)
        self.roles.clear()
        for row in result:
            self.roles.append(row['role'])

        select_stmt = f'''
            SELECT student_id
                FROM user_x_students
                WHERE user_id = {self.id}
        '''
        result = execute_read(self.db, select_stmt)
        self.student_ids.clear()
        if result is not None:
            for row in result:
                self.student_ids.append(row['student_id'])
        return True

    def create(self):
        insert_stmt = f'''
            INSERT INTO user (id, given_name, family_name, full_name, google_email, picture)
                VALUES ({self.id}, "{self.given_name}", "{self.family_name}", "{self.full_name}", "{self.google_email}", "{self.picture}");
        '''
        execute_write(self.db, insert_stmt)

        if self.id == 107146654681983684193:
            self.roles.clear()
            self.roles.append("GUARDIAN")
            self.roles.append("INSTRUCTOR")
            self.roles.append("ADMIN")
            insert_stmt = f'''
                INSERT INTO user_x_roles (user_id, role)
                    VALUES ({self.id}, "GUARDIAN"), ({self.id}, "INSTRUCTOR"), ({self.id}, "ADMIN");
            '''
            execute_write(self.db, insert_stmt)
        else:
            self.roles.clear()
            self.roles.append("GUARDIAN")
            insert_stmt = f'''
                INSERT INTO user_x_roles (user_id, role)
                    VALUES ({self.id}, "GUARDIAN");
            '''
            execute_write(self.db, insert_stmt)

    def update(self):
        update_stmt = f'''
            UPDATE user
                SET given_name="{self.given_name}", family_name="{self.family_name}",
                    full_name="{self.full_name}", google_email="{self.google_email}", picture="{self.picture}"
                WHERE id = {self.id};
        '''
        execute_write(self.db, update_stmt)

        delete_stmt = f'''
            DELETE FROM user_x_roles WHERE user_id={self.id};
        '''
        execute_write(self.db, delete_stmt)
        for role in self.roles:
            insert_stmt = f'''
                INSERT INTO user_x_roles (user_id, role)
                    VALUES ({self.id}, "{role}");
            '''
            execute_write(self.db, insert_stmt)

        delete_stmt = f'''
            DELETE FROM user_x_students WHERE user_id={self.id};
        '''
        execute_write(self.db, delete_stmt)
        for student_id in self.student_ids:
            insert_stmt = f'''
                INSERT INTO user_x_students (user_id, student_id)
                    VALUES ({self.id}, "{student_id}");
            '''
            execute_write(self.db, insert_stmt)

    def delete(self):
        delete_stmt = f'''
            DELETE FROM user_x_roles
                WHERE user_id = {self.id};
        '''
        execute_write(self.db, delete_stmt)
        delete_stmt = f'''
            DELETE FROM user_x_students
                WHERE user_id = {self.id};
        '''
        execute_write(self.db, delete_stmt)
        delete_stmt = f'''
            DELETE FROM user
                WHERE id = {self.id};
        '''
        execute_write(self.db, delete_stmt)

    def __init__(self, **data):
        super().__init__(**data)
        if not self.load():
            self.create()



