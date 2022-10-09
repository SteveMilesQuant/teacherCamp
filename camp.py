import copy
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from db import execute_read, execute_write
from program import Program
from user import User


class Camp(BaseModel):
    id: Optional[int]
    program_id: Optional[int]
    program: Optional[Program]
    instructors: Optional[Dict[int,User]] = {}
    primary_instructor: Optional[User] = None
    db: Optional[Any]

    def _load(self) -> bool:
        select_stmt = f'''
            SELECT *
                FROM camp
                WHERE id = {self.id}
        '''
        result = execute_read(self.db, select_stmt)
        if result is None:
            return False;
        row = result[0] # should only be one
        self.program_id = row['program_id']

        select_stmt = f'''
            SELECT user_id, is_primary
                FROM camp_x_instructors
                WHERE camp_id = {self.id}
        '''
        result = execute_read(self.db, select_stmt)
        self.instructors.clear()
        if result is not None:
            for row in result:
                instructor = User(db = self.db, id = row['user_id'])
                self.instructors[instructor.id] = instructor
                if row['is_primary']:
                    self.primary_instructor = instructor
        return True

    def _create(self):
        insert_stmt = f'''
            INSERT INTO camp (program_id)
                VALUES ({self.program_id});
        '''
        self.id = execute_write(self.db, insert_stmt)

    def __init__(self, **data):
        super().__init__(**data)
        if self.id is None:
            self._create()
        elif not self._load():
            self._create()

    def delete(self):
        delete_stmt = f'''
            DELETE FROM camp_x_instructors
                WHERE camp_id = {self.id};
        '''
        execute_write(self.db, delete_stmt)
        delete_stmt = f'''
            DELETE FROM camp
                WHERE id = {self.id};
        '''
        execute_write(self.db, delete_stmt)

    def add_instructor(self, user_id: int):
        if self.instructors.get(user_id) is None:
            instructor = User(db = self.db, id = user_id)
            if instructor is not None and "INSTRUCTOR" in instructor.roles:
                instructor.db = None # don't allow User updates from a Camp
                is_primary = (len(self.instructors) == 0)
                self.instructors[instructor.id] = instructor
                if is_primary:
                    self.primary_instructor = instructor
                insert_stmt = f'''
                    INSERT INTO camp_x_instructors (camp_id, user_id, is_primary)
                        VALUES ({self.id}, {instructor.id}, {is_primary});
                '''
                execute_write(self.db, insert_stmt)

    def make_instructor_primary(self, user_id: int):
        instructor = self.instructors.get(user_id)
        if instructor is not None and (self.primary_instructor is None or instructor.id != self.primary_instructor.id):
            update_stmt = f'''
                UPDATE camp_x_instructors
                    SET is_primary=FALSE
                    WHERE camp_id = {self.id} and user_id = {self.primary_instructor.id};
            '''
            execute_write(self.db, update_stmt)
            update_stmt = f'''
                UPDATE camp_x_instructors
                    SET is_primary=TRUE
                    WHERE camp_id = {self.id} and user_id = {instructor.id};
            '''
            execute_write(self.db, update_stmt)
            self.primary_instructor = instructor

    def remove_instructor(self, user_id: int):
        instructor = self.instructors.pop(user_id) # not really a tuple
        if instructor is not None:
            if self.primary_instructor is not None and self.primary_instructor.id == instructor.id:
                if len(self.instructors) > 0:
                    first_instructor = self.instructors.values()[0]
                    self.make_instructor_primary(first_instructor)
                else:
                    self.primary_instructor = None
            delete_stmt = f'''
                DELETE FROM camp_x_instructors
                    VALUES camp_id = {self.id} and user_id = {instructor.id}
            '''
            execute_write(self.db, insert_stmt)

    def load_program(self):
        self.program = Program(db = self.db, id = self.program_id)
        self.program.db = None # don't allow Program updates from a Camp


def load_all_camps(db: Any, camps: Dict[int,Camp], force_load=False):
    if not force_load and len(camps) > 0: # for now, only load once
        return None
    select_stmt = f'''
        SELECT id
            FROM camp
    '''
    result = execute_read(db, select_stmt)
    if result is not None:
        for row in result:
            camp = Camp(db = db, id = row['id'])
            camp.load_program()
            camp.db = None # don't allow update from this list
            camps[camp.id] = camp


