from db import execute_read, execute_write
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import date
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
    id: Optional[int] = None  # we use AUTOMATICINCREMENT on create, so this wouldn't be necessary then
    google_id: Optional[int]
    given_name: str
    family_name: str
    full_name: str
    google_email: str
    picture: str
    db: Any
    roles: Optional[List[str]] = []
    students: Optional[Dict[int, Student]] = {}
    programs: Optional[Dict[int, Program]] = {}

    def load(self) -> bool:
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

    def create(self):
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
        for student_id in self.students.keys():
            insert_stmt = f'''
                INSERT INTO user_x_students (user_id, student_id)
                    VALUES ({self.id}, "{student_id}");
            '''
            execute_write(self.db, insert_stmt)
            
        delete_stmt = f'''
            DELETE FROM user_x_programs WHERE user_id={self.id};
        '''
        execute_write(self.db, delete_stmt)
        for program_id in self.programs.keys():
            insert_stmt = f'''
                INSERT INTO user_x_programs (user_id, program_id)
                    VALUES ({self.id}, "{program_id}");
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

    def load_students(self):
        for student_id, student in self.students.items():
            self.students[student_id] = Student(id=student_id, db=self.db)

    def remove_student(self, student_id: int):
        self.load_students()
        student = self.students.get(student_id)
        if student is not None:
            del self.students[student_id]
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

    def remove_program(self, program_id: int):
        self.load_programs()
        program = self.programs.get(program_id)
        if program is not None:
            del self.programs[program_id]
            # If no other instructors have this program, fully delete it
            select_stmt = f'''
                SELECT program_id
                    FROM user_x_programs
                    WHERE program_id = {program_id}
            '''
            result = execute_read(self.db, select_stmt)
            if result is None:
                program.delete()


