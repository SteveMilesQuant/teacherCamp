import copy
from db import execute_read, execute_write
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import date
from program import GradeLevel


class Student(BaseModel):
    id: Optional[int] = None  # we use AUTOMATICINCREMENT on create, so this wouldn't be necessary then
    name: Optional[str] = None
    birthdate: Optional[date] = None
    grade_level: Optional[GradeLevel] = None
    school: Optional[str] = ""
    db: Any

    def _load(self) -> bool:
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
        self.grade_level = GradeLevel(row['grade_level'])
        self.school = row['school']
        return True

    def _create(self):
        sql_date = self.birthdate.strftime('%Y-%m-%d')
        insert_stmt = f'''
            INSERT INTO student (name, birthdate, grade_level, school)
                VALUES ("{self.name}", "{sql_date}", {self.grade_level.value}, "{self.school}");
        '''
        self.id = execute_write(self.db, insert_stmt)

    def __init__(self, **data):
        super().__init__(**data)
        if self.id is None:
            self._create()
        elif not self._load():
            self._create()

    def update_basic(self,
            name: Optional[str] = None,
            birthdate: Optional[date] = None,
            grade_level: Optional[GradeLevel] = None,
            school: Optional[str] = None
        ):
        if name is not None:
            self.name = name
        if birthdate is not None:
            if type(birthdate) == str:
                year, month, day = birthdate.split('-')
                self.birthdate = date(int(year), int(month), int(day))
            else:
                self.birthdate = birthdate
        if grade_level is not None:
            if type(grade_level) == int:
                self.grade_level = GradeLevel(grade_level)
            elif type(grade_level) == str:
                self.grade_level = GradeLevel(int(grade_level))
            else:
                self.grade_level = grade_level
        if school is not None:
            self.school = school
        sql_date = self.birthdate.strftime('%Y-%m-%d')
        update_stmt = f'''
            UPDATE student
                SET name="{self.name}", birthdate="{sql_date}",
                    grade_level={self.grade_level.value}, school="{self.school}"
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

    def deepcopy(self):
        save_db = self.db
        self.db = None
        deep_copy = copy.deepcopy(self)
        self.db = save_db
        return deep_copy


