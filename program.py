import copy
from enum import Enum
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from db import execute_read, execute_write


class Level(BaseModel):
    id: Optional[int]
    title: Optional[str]
    description: Optional[str] = ''
    list_index: Optional[int] = 0
    db: Any

    def load(self) -> bool:
        select_stmt = f'''
            SELECT *
                FROM level
                WHERE id = {self.id}
        '''
        result = execute_read(self.db, select_stmt)
        if result is None:
            return False;
        row = result[0] # should only be one
        self.title = row['title']
        self.description = row['description']
        self.list_index = row['list_index']
        return True

    def create(self):
        insert_stmt = f'''
            INSERT INTO level (title, description, list_index)
                VALUES ("{self.title}", "{self.description}", {self.list_index});
        '''
        self.id = execute_write(self.db, insert_stmt)

    def update(self):
        update_stmt = f'''
            UPDATE level
                SET title="{self.title}",
                    description="{self.description}",
                    list_index={self.list_index}
                WHERE id = {self.id};
        '''
        execute_write(self.db, update_stmt)

    def delete(self):
        delete_stmt = f'''
            DELETE FROM program_x_levels
                WHERE level_id = {self.id};
        '''
        execute_write(self.db, delete_stmt)
        delete_stmt = f'''
            DELETE FROM level
                WHERE id = {self.id};
        '''
        execute_write(self.db, delete_stmt)

    def __init__(self, **data):
        super().__init__(**data)
        if self.id is None:
            self.create()
        elif not self.load():
            self.create()

    def deepcopy(self):
        save_db = self.db
        self.db = None
        deep_copy = copy.deepcopy(self)
        self.db = save_db
        return deep_copy


class Program(BaseModel):
    id: Optional[int]
    title: Optional[str]
    grade_range: Optional[tuple[int,int]]
    tags: Optional[str] = ''
    description: Optional[str] = ''
    db: Any
    levels: Optional[Dict[int, Level]] = {}

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
        self.tags = row['tags']
        self.description = row['description']

        select_stmt = f'''
            SELECT level_id
                FROM program_x_levels
                WHERE program_id = {self.id}
        '''
        result = execute_read(self.db, select_stmt)
        self.levels.clear()
        if result is not None:
            for row in result:
                self.levels[row['level_id']] = None
        return True

    def create(self):
        insert_stmt = f'''
            INSERT INTO program (title, from_grade, to_grade, tags, description)
                VALUES ("{self.title}", {self.grade_range[0]}, {self.grade_range[1]}, "{self.tags}", "{self.description}");
        '''
        self.id = execute_write(self.db, insert_stmt)

    def update(self):
        update_stmt = f'''
            UPDATE program
                SET title="{self.title}",
                    from_grade={self.grade_range[0]},
                    to_grade={self.grade_range[1]},
                    tags="{self.tags}",
                    description="{self.description}"
                WHERE id = {self.id};
        '''
        execute_write(self.db, update_stmt)

        delete_stmt = f'''
            DELETE FROM program_x_levels WHERE program_id={self.id};
        '''
        execute_write(self.db, delete_stmt)
        for level_id in self.levels.keys():
            insert_stmt = f'''
                INSERT INTO program_x_levels (program_id, level_id)
                    VALUES ({self.id}, "{level_id}");
            '''
            execute_write(self.db, insert_stmt)

    def delete(self):
        # Levels are not shared across programs, so they are safe to delete when we delete the program
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
        delete_stmt = f'''
            DELETE FROM program_x_levels
                WHERE program_id = {self.id};
        '''
        execute_write(self.db, delete_stmt)

    def __init__(self, **data):
        super().__init__(**data)
        if self.id is None:
            self.create()
        elif not self.load():
            self.create()

    def load_levels(self):
        for level_id in self.levels.keys():
            self.levels[level_id] = Level(id=level_id, db=self.db)

    def deepcopy(self):
        save_db = self.db
        self.db = None
        for level in self.levels.values():
            if level is not None:
                level.db = None
        deep_copy = copy.deepcopy(self)
        self.db = save_db
        for level in self.levels.values():
            if level is not None:
                level.db = save_db
        return deep_copy


