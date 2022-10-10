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

    def _load(self, db: Any) -> bool:
        select_stmt = f'''
            SELECT *
                FROM student
                WHERE id = {self.id}
        '''
        result = execute_read(db, select_stmt)
        if result is None:
            return False;
        row = result[0] # should only be one
        self.name = row['name']
        year, month, day = row['birthdate'].split('-')
        self.birthdate = date(int(year), int(month), int(day))
        self.grade_level = GradeLevel(row['grade_level'])
        return True

    def _create(self, db: Any):
        sql_date = self.birthdate.strftime('%Y-%m-%d')
        insert_stmt = f'''
            INSERT INTO student (name, birthdate, grade_level)
                VALUES ("{self.name}", "{sql_date}", {self.grade_level.value});
        '''
        self.id = execute_write(db, insert_stmt)

    def __init__(self, db: Any, **data):
        super().__init__(**data)
        if self.id is None:
            self._create(db = db)
        elif not self._load(db = db):
            self._create(db = db)

    def update_basic(self, db: Any,
            name: Optional[str] = None,
            birthdate: Optional[date] = None,
            grade_level: Optional[GradeLevel] = None
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
        sql_date = self.birthdate.strftime('%Y-%m-%d')
        update_stmt = f'''
            UPDATE student
                SET name="{self.name}", birthdate="{sql_date}",
                    grade_level={self.grade_level.value}
                WHERE id = {self.id};
        '''
        execute_write(db, update_stmt)

    def delete(self, db: Any):
        delete_stmt = f'''
            DELETE FROM user_x_students
                WHERE student_id = {self.id};
        '''
        execute_write(db, delete_stmt)
        delete_stmt = f'''
            DELETE FROM student
                WHERE id = {self.id};
        '''
        execute_write(db, delete_stmt)


