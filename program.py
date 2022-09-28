from enum import Enum
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from db import execute_read, execute_write


class Duration(Enum):
    half = 0
    full = 1


class Program(BaseModel):
    id: Optional[int]
    title: Optional[str]
    grade_range: Optional[tuple[int,int]]
    duration: Optional[Duration]
    tags: Optional[str] = ''
    description: Optional[str] = ''
    db: Any
    
    def load(self) -> bool:
        select_stmt = f'''
            SELECT *
                FROM program
                WHERE id = {self.id}
        '''
        result = execute_read(self.db, select_stmt)
        if result is None:
            return False;
        row = result[0] # should only be one
        self.title = row['title']
        self.grade_range = (row['from_grade'], row['to_grade'])
        self.duration = Duration[row['duration']]
        self.tags = row['tags']
        self.description = row['description']
        return True

    def create(self):
        insert_stmt = f'''
            INSERT INTO program (title, from_grade, to_grade, duration, tags, description)
                VALUES ("{self.title}", {self.grade_range[0]}, {self.grade_range[1]}, "{self.duration.name}", "{self.tags}", "{self.description}");
        '''
        self.id = execute_write(self.db, insert_stmt)

    def update(self):
        update_stmt = f'''
            UPDATE program
                SET title="{self.title}",
                    from_grade={self.grade_range[0]},
                    to_grade={self.grade_range[1]},
                    duration="{self.duration.name}"
                    tags="{self.tags}"
                    description="{self.description}"
                WHERE id = {self.id};
        '''
        execute_write(self.db, update_stmt)

    def delete(self):
        delete_stmt = f'''
            DELETE FROM user_x_programs
                WHERE program_id = {self.id};
        '''
        execute_write(self.db, delete_stmt)
        delete_stmt = f'''
            DELETE FROM program
                WHERE id = {self.id};
        '''
        execute_write(self.db, delete_stmt)

    def __init__(self, **data):
        super().__init__(**data)
        if self.id is None:
            self.create()
        elif not self.load():
            self.create()


