from db import execute_read, execute_write
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from student import Student
from program import Program


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


class User(BaseModel):
    id: Optional[int] = None  # we use AUTOMATICINCREMENT on create, so this wouldn't be necessary then
    google_id: Optional[int]
    given_name: Optional[str]
    family_name: Optional[str]
    full_name: Optional[str]
    google_email: Optional[str]
    picture: Optional[str]
    db: Any
    roles: Optional[List[str]] = []
    students: Optional[Dict[int, Student]] = {}
    programs: Optional[Dict[int, Program]] = {}

    def _load(self) -> bool:
        if self.id is None:
            select_stmt = f'''
                SELECT *
                    FROM user
                    WHERE google_id = {self.google_id}
            '''
            result = execute_read(self.db, select_stmt)
            if result is not None:
                row = result[0] # should only be one
                self.id = row['id']
        else:
            select_stmt = f'''
                SELECT *
                    FROM user
                    WHERE id = {self.id}
            '''
            result = execute_read(self.db, select_stmt)
        if result is None:
            return False;
        row = result[0] # should only be one
        self.google_id = row['google_id']
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
        self.students.clear()
        if result is not None:
            for row in result:
                self.students[row['student_id']] = None

        select_stmt = f'''
            SELECT program_id
                FROM user_x_programs
                WHERE user_id = {self.id}
        '''
        result = execute_read(self.db, select_stmt)
        self.programs.clear()
        if result is not None:
            for row in result:
                self.programs[row['program_id']] = None
        return True

    def _create(self):
        insert_stmt = f'''
            INSERT INTO user (google_id, given_name, family_name, full_name, google_email, picture)
                VALUES ({self.google_id}, "{self.given_name}", "{self.family_name}", "{self.full_name}", "{self.google_email}", "{self.picture}");
        '''
        self.id = execute_write(self.db, insert_stmt)

        if self.id == 1:
            # first user gets all roles
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
            # new users are only guardians - admin must upgrade them
            self.roles.clear()
            self.roles.append("GUARDIAN")
            insert_stmt = f'''
                INSERT INTO user_x_roles (user_id, role)
                    VALUES ({self.id}, "GUARDIAN");
            '''
            execute_write(self.db, insert_stmt)

    def __init__(self, **data):
        super().__init__(**data)
        if not self._load():
            self._create()

    def update_basic(self,
            given_name: Optional[str] = None,
            family_name: Optional[str] = None,
            full_name: Optional[str] = None,
            google_email: Optional[str] = None,
            picture: Optional[str] = None
        ):
        if given_name is not None:
            self.given_name = given_name
        if family_name is not None:
            self.family_name = family_name
        if full_name is not None:
            self.full_name = full_name
        if google_email is not None:
            self.google_email = google_email
        if picture is not None:
            self.picture = picture
        update_stmt = f'''
            UPDATE user
                SET given_name="{self.given_name}", family_name="{self.family_name}",
                    full_name="{self.full_name}", google_email="{self.google_email}", picture="{self.picture}"
                WHERE id = {self.id};
        '''
        execute_write(self.db, update_stmt)

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

    def add_role(self, role: str):
        if role not in self.roles:
            self.roles.append(role)
            insert_stmt = f'''
                INSERT INTO user_x_roles (user_id, role)
                    VALUES ({self.id}, "{role}");
            '''
            execute_write(self.db, insert_stmt)

    def remove_role(self, role: str):
        del_role = self.roles.pop(role)
        if del_role is not None:
            delete_stmt = f'''
                DELETE FROM user_x_roles WHERE user_id={self.id} and role="{role}";
            '''
            execute_write(self.db, delete_stmt)

    def load_students(self):
        for student_id in self.students.keys():
            self.students[student_id] = Student(id=student_id, db=self.db)

    def add_student(self, student_id: int):
        self.students[student_id] = None
        insert_stmt = f'''
            INSERT INTO user_x_students (user_id, student_id)
                VALUES ({self.id}, "{student_id}");
        '''
        execute_write(self.db, insert_stmt)

    def remove_student(self, student_id: int):
        self.load_students()
        student = self.students.pop(student_id)
        if student is not None:
            delete_stmt = f'''
                DELETE FROM user_x_students
                    WHERE user_id = {self.id} and student_id = {student_id};
            '''
            execute_write(self.db, delete_stmt)

            # If no other guardians have this student, fully delete them
            select_stmt = f'''
                SELECT student_id
                    FROM user_x_students
                    WHERE student_id = {student_id}
            '''
            result = execute_read(self.db, select_stmt)
            if result is None:
                student.delete()

    def load_programs(self):
        for program_id, program in self.programs.items():
            self.programs[program_id] = Program(id=program_id, db=self.db)

    def add_program(self, program_id: int):
        self.programs[program_id] = None
        insert_stmt = f'''
            INSERT INTO user_x_programs (user_id, program_id)
                VALUES ({self.id}, "{program_id}");
        '''
        execute_write(self.db, insert_stmt)

    def remove_program(self, program_id: int):
        self.load_programs()
        program = self.programs.pop(program_id)
        if program is not None:
            delete_stmt = f'''
                DELETE FROM user_x_programs
                    WHERE user_id = {self.id} and program_id = {program_id};
            '''
            execute_write(self.db, delete_stmt)

            # If no other instructors have this program, fully delete it
            select_stmt = f'''
                SELECT program_id
                    FROM user_x_programs
                    WHERE program_id = {program_id}
            '''
            result = execute_read(self.db, select_stmt)
            if result is None:
                program.delete()


def load_all_users_by_role(db: Any, users: Dict[int,User], role: str, force_load=False):
    if not force_load and len(users) > 0: # for now, only load once
        return None
    select_stmt = f'''
        SELECT id
            FROM user
            WHERE id IN (SELECT id from user_x_roles WHERE role = "{role}")
    '''
    result = execute_read(db, select_stmt)
    if result is not None:
        for row in result:
            user = User(db = db, id = row['id'])
            user.db = None # don't allow update from this list
            users[user.id] = user
    
