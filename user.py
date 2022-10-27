import pandas
from db import execute_read, execute_write
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from student import Student
from program import Program, GradeLevel
from filtertable import FilterTable, Checkboxes, DoubleRange


class Role(BaseModel):
    name: str
    permissible_endpoints: Optional[Dict[str, str]] = {}

    def __init__(self, db: Any, **data):
        super().__init__(**data)
        self.permissible_endpoints.clear()
        select_stmt = f'''
            SELECT endpoint, endpoint_title
                FROM role_permissions
                WHERE role = "{self.name}"
        '''
        result = execute_read(db, select_stmt)
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
        all_roles[role_name] = Role(db = db, name = role_name)
    return all_roles


class User(BaseModel):
    id: Optional[int] = None  # we use AUTOMATICINCREMENT on create, so this wouldn't be necessary then
    google_id: Optional[int]
    given_name: Optional[str]
    family_name: Optional[str]
    full_name: Optional[str]
    picture: Optional[str]
    roles: Optional[List[str]] = []
    email_addresses: Optional[List[str]] = []
    primary_email_address_index: Optional[int] = 0
    students: Optional[Dict[int, Student]] = {}
    program_ids: Optional[List[int]] = []

    def _load(self, db: Any) -> bool:
        if self.id is None:
            select_stmt = f'''
                SELECT *
                    FROM user
                    WHERE google_id = {self.google_id}
            '''
            result = execute_read(db, select_stmt)
            if result is not None:
                row = result[0] # should only be one
                self.id = row['id']
        else:
            select_stmt = f'''
                SELECT *
                    FROM user
                    WHERE id = {self.id}
            '''
            result = execute_read(db, select_stmt)
        if result is None:
            return False;
        row = result[0] # should only be one
        self.google_id = row['google_id']
        self.given_name = row['given_name']
        self.family_name = row['family_name']
        self.full_name = row['full_name']
        self.picture = row['picture']

        select_stmt = f'''
            SELECT role
                FROM user_x_roles
                WHERE user_id = {self.id}
        '''
        result = execute_read(db, select_stmt)
        self.roles.clear()
        for row in result:
            self.roles.append(row['role'])

        select_stmt = f'''
            SELECT email_address, is_primary
                FROM user_x_email_addresses
                WHERE user_id = {self.id}
        '''
        result = execute_read(db, select_stmt)
        self.email_addresses.clear()
        for row_idx, row in enumerate(result):
            self.email_addresses.append(row['email_address'])
            if row['is_primary']:
                self.primary_email_address_index = row_idx

        select_stmt = f'''
            SELECT student_id
                FROM user_x_students
                WHERE user_id = {self.id}
        '''
        result = execute_read(db, select_stmt)
        self.students.clear()
        if result is not None:
            for row in result:
                self.students[row['student_id']] = None

        select_stmt = f'''
            SELECT program_id
                FROM user_x_programs
                WHERE user_id = {self.id}
        '''
        result = execute_read(db, select_stmt)
        self.program_ids.clear()
        if result is not None:
            for row in result:
                self.program_ids.append(row['program_id'])
        return True

    def _create(self, db: Any):
        insert_stmt = f'''
            INSERT INTO user (google_id, given_name, family_name, full_name, picture)
                VALUES ({self.google_id}, "{self.given_name}", "{self.family_name}", "{self.full_name}", "{self.picture}");
        '''
        self.id = execute_write(db, insert_stmt)

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
            execute_write(db, insert_stmt)
        else:
            # new users are only guardians - admin must upgrade them
            self.roles.clear()
            self.roles.append("GUARDIAN")
            insert_stmt = f'''
                INSERT INTO user_x_roles (user_id, role)
                    VALUES ({self.id}, "GUARDIAN");
            '''
            execute_write(db, insert_stmt)

    def __init__(self, db: Any, **data):
        super().__init__(**data)
        if not self._load(db = db):
            self._create(db = db)

    def update_basic(self, db: Any,
            given_name: Optional[str] = None,
            family_name: Optional[str] = None,
            full_name: Optional[str] = None,
            picture: Optional[str] = None
        ):
        if given_name is not None:
            self.given_name = given_name
        if family_name is not None:
            self.family_name = family_name
        if full_name is not None:
            self.full_name = full_name
        if picture is not None:
            self.picture = picture
        update_stmt = f'''
            UPDATE user
                SET given_name="{self.given_name}", family_name="{self.family_name}",
                    full_name="{self.full_name}", picture="{self.picture}"
                WHERE id = {self.id};
        '''
        execute_write(db, update_stmt)

    def delete(self, db: Any):
        delete_stmt = f'''
            DELETE FROM user_x_roles
                WHERE user_id = {self.id};
        '''
        execute_write(db, delete_stmt)
        delete_stmt = f'''
            DELETE FROM user_x_email_addresses
                WHERE user_id = {self.id};
        '''
        execute_write(db, delete_stmt)
        delete_stmt = f'''
            DELETE FROM user_x_students
                WHERE user_id = {self.id};
        '''
        execute_write(db, delete_stmt)
        delete_stmt = f'''
            DELETE FROM user
                WHERE id = {self.id};
        '''
        execute_write(db, delete_stmt)

    def add_role(self, db: Any, role: str):
        if role not in self.roles:
            self.roles.append(role)
            insert_stmt = f'''
                INSERT INTO user_x_roles (user_id, role)
                    VALUES ({self.id}, "{role}");
            '''
            execute_write(db, insert_stmt)

    def remove_role(self, db: Any, role: str):
        del_role = self.roles.pop(role)
        if del_role is not None:
            delete_stmt = f'''
                DELETE FROM user_x_roles WHERE user_id={self.id} and role="{role}";
            '''
            execute_write(db, delete_stmt)

    def make_email_address_primary(self, db: Any, email_address: str):
        try:
            old_primary_address = self.email_addresses[self.primary_email_address_index]
            email_address_index = self.email_addresses.index(email_address)
            update_stmt = f'''
                UPDATE user
                    SET is_primary=FALSE
                    WHERE ser_id={self.id} and email_address="{old_primary_address}";
            '''
            execute_write(db, update_stmt)
            update_stmt = f'''
                UPDATE user
                    SET is_primary=TRUE
                    WHERE ser_id={self.id} and email_address="{email_address}";
            '''
            execute_write(db, update_stmt)
            self.primary_email_address_index = email_address_index
        except ValueError:
            pass # not found - do nothing

    def add_email_address(self, db: Any, email_address: str):
        if email_address not in self.email_addresses:
            if len(self.email_addresses) == 0:
                is_primary = True
                self.primary_email_address_index = 0
            else:
                is_primary = False
            self.email_addresses.append(email_address)
            insert_stmt = f'''
                INSERT INTO user_x_email_addresses (user_id, email_address, is_primary)
                    VALUES ({self.id}, "{email_address}", {is_primary});
            '''
            execute_write(db, insert_stmt)

    def remove_email_address(self, db: Any, email_address: str):
        del_email_address = self.email_addresses.pop(email_address)
        if del_email_address is not None:
            delete_stmt = f'''
                DELETE FROM user_x_email_addresses WHERE user_id={self.id} and email_address="{email_address}";
            '''
            execute_write(db, delete_stmt)

    def load_students(self, db: Any):
        for student_id in self.students.keys():
            self.students[student_id] = Student(id=student_id, db=db)

    def add_student(self, db: Any, student_id: int):
        self.students[student_id] = None
        insert_stmt = f'''
            INSERT INTO user_x_students (user_id, student_id)
                VALUES ({self.id}, "{student_id}");
        '''
        execute_write(db, insert_stmt)

    def remove_student(self, db: Any, student_id: int):
        self.load_students(db = db)
        student = self.students.pop(student_id)
        if student is not None:
            delete_stmt = f'''
                DELETE FROM user_x_students
                    WHERE user_id = {self.id} and student_id = {student_id};
            '''
            execute_write(db, delete_stmt)

            # If no other guardians have this student, fully delete them
            select_stmt = f'''
                SELECT student_id
                    FROM user_x_students
                    WHERE student_id = {student_id}
            '''
            result = execute_read(db, select_stmt)
            if result is None:
                student.delete(db = db)

    def load_programs_table(self, db: Any) -> FilterTable:
        select_stmt = f'''
            SELECT t2.*
                FROM user_x_programs as t1, program as t2
                WHERE t1.user_id = {self.id} and t1.program_id = t2.id
        '''
        dataframe = pandas.read_sql_query(select_stmt, db)
        dataframe['grade_range'] = dataframe['from_grade'].copy()
        for row_idx, row in dataframe.iterrows():
            grade_range = f'{GradeLevel(row["grade_range"]).html_display()} to {GradeLevel(row["to_grade"]).html_display()}'
            dataframe.at[row_idx,'grade_range'] = grade_range
        filter_table = FilterTable(base_dataframe=dataframe)
        dataframe = filter_table.base_dataframe
        dataframe.columns[dataframe.columns.get_loc('title')].display = True
        dataframe.columns[dataframe.columns.get_loc('tags')].display = True
        dataframe.columns[dataframe.columns.get_loc('grade_range')].display = True
        filter_table.filters.append(Checkboxes(display_column='tags', source_column='tags'))
        filter_table.filters.append(DoubleRange(display_column='grade_range', source_columns=('from_grade','to_grade')))
        return filter_table

    def add_program(self, db: Any, program_id: int):
        if program_id not in self.program_ids:
            self.program_ids.append(program_id)
            insert_stmt = f'''
                INSERT INTO user_x_programs (user_id, program_id)
                    VALUES ({self.id}, "{program_id}");
            '''
            execute_write(db, insert_stmt)

    def remove_program(self, db: Any, program_id: int):
        try:
            self.program_ids.remove(program_id)
        except ValueError:
            return # not found is okay, but we should leave

        delete_stmt = f'''
            DELETE FROM user_x_programs
                WHERE user_id = {self.id} and program_id = {program_id};
        '''
        execute_write(db, delete_stmt)
        # If no other instructors have this program, fully delete it
        select_stmt = f'''
            SELECT program_id
                FROM user_x_programs
                WHERE program_id = {program_id}
        '''
        result = execute_read(db, select_stmt)
        if result is None:
            program = Program(db = db, id = program_id)
            program.delete(db = db)


def load_all_users_by_role(db: Any, role: str, users: Dict[int,User]):
    select_stmt = f'''
        SELECT id
            FROM user
            WHERE id IN (SELECT id from user_x_roles WHERE role = "{role}")
    '''
    result = execute_read(db, select_stmt)
    if result is not None:
        for row in result:
            user = User(db = db, id = row['id'])
            users[user.id] = user

