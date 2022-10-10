from enum import Enum
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from db import execute_read, execute_write


class GradeLevel(Enum):
    K = 0
    First = 1
    Second = 2
    Third = 3
    Fourth = 4
    Fifth = 5
    Sixth = 6
    Seventh = 7
    Eighth = 8
    Freshman = 9
    Sophopmore = 10
    Junior = 11
    Senior = 12

    def html_display(self) -> str:
        if self.value == 0:
            return str(self.name)
        return str(self.value)


class Level(BaseModel):
    id: Optional[int]
    title: Optional[str]
    description: Optional[str] = ''
    list_index: Optional[int] = 0

    def _load(self, db: Any) -> bool:
        select_stmt = f'''
            SELECT *
                FROM level
                WHERE id = {self.id}
        '''
        result = execute_read(db, select_stmt)
        if result is None:
            return False;
        row = result[0] # should only be one
        self.title = row['title']
        self.description = row['description']
        self.list_index = row['list_index']
        return True

    def _create(self, db: Any):
        insert_stmt = f'''
            INSERT INTO level (title, description, list_index)
                VALUES ("{self.title}", "{self.description}", {self.list_index});
        '''
        self.id = execute_write(db, insert_stmt)

    def __init__(self, db: Any, **data):
        super().__init__(**data)
        if self.id is None:
            self._create(db = db)
        elif not self._load(db = db):
            self._create(db = db)

    def update_basic(self, db: Any,
            title: Optional[str] = None,
            description: Optional[str] = None,
            list_index: Optional[int] = None
        ):
        if title is not None:
            self.title = title
        if description is not None:
            self.description = description
        if list_index is not None:
            self.list_index = list_index
        update_stmt = f'''
            UPDATE level
                SET title="{self.title}",
                    description="{self.description}",
                    list_index={self.list_index}
                WHERE id = {self.id};
        '''
        execute_write(db, update_stmt)

    def delete(self, db: Any):
        delete_stmt = f'''
            DELETE FROM program_x_levels
                WHERE level_id = {self.id};
        '''
        execute_write(db, delete_stmt)
        delete_stmt = f'''
            DELETE FROM level
                WHERE id = {self.id};
        '''
        execute_write(db, delete_stmt)


class Program(BaseModel):
    id: Optional[int]
    title: Optional[str]
    grade_range: Optional[List[GradeLevel]]
    tags: Optional[str] = ''
    description: Optional[str] = ''
    levels: Optional[Dict[int, Level]] = {}

    def _load(self, db: Any) -> bool:
        select_stmt = f'''
            SELECT *
                FROM program
                WHERE id = {self.id}
        '''
        result = execute_read(db, select_stmt)
        if result is None:
            return False;
        row = result[0] # should only be one
        self.title = row['title']
        self.grade_range = [GradeLevel(row['from_grade']), GradeLevel(row['to_grade'])]
        self.tags = row['tags']
        self.description = row['description']

        select_stmt = f'''
            SELECT level_id
                FROM program_x_levels
                WHERE program_id = {self.id}
        '''
        result = execute_read(db, select_stmt)
        self.levels.clear()
        if result is not None:
            for row in result:
                self.levels[row['level_id']] = None
        return True

    def _create(self, db: Any):
        self.tags = self.tags.lower()
        insert_stmt = f'''
            INSERT INTO program (title, from_grade, to_grade, tags, description)
                VALUES ("{self.title}", {self.grade_range[0].value}, {self.grade_range[1].value}, "{self.tags}", "{self.description}");
        '''
        self.id = execute_write(db, insert_stmt)

    def __init__(self, db: Any, **data):
        super().__init__(**data)
        if self.id is None:
            self._create(db = db)
        elif not self._load(db = db):
            self._create(db = db)

    def update_basic(self, db: Any,
            title: Optional[str] = None,
            from_grade: Optional[int] = None,
            to_grade: Optional[int] = None,
            tags: Optional[str] = None,
            description: Optional[str] = None
        ):
        if title is not None:
            self.title = title
        if from_grade is not None:
            if type(from_grade) == str:
                self.grade_range[0] = GradeLevel(int(from_grade))
            elif type(from_grade) == int:
                self.grade_range[0] = GradeLevel(from_grade)
            else:
                self.grade_range[0] = from_grade
        if to_grade is not None:
            if type(to_grade) == str:
                self.grade_range[1] = GradeLevel(int(to_grade))
            elif type(to_grade) == int:
                self.grade_range[1] = GradeLevel(to_grade)
            else:
                self.grade_range[1] = to_grade
        if tags is not None:
            self.tags = tags.lower()
        if description is not None:
            self.description = description
        update_stmt = f'''
            UPDATE program
                SET title="{self.title}",
                    from_grade={self.grade_range[0].value},
                    to_grade={self.grade_range[1].value},
                    tags="{self.tags}",
                    description="{self.description}"
                WHERE id = {self.id};
        '''
        execute_write(db, update_stmt)

    def delete(self, db: Any):
        # Levels are not shared across programs, so they are safe to delete when we delete the program
        delete_stmt = f'''
            DELETE FROM user_x_programs
                WHERE program_id = {self.id};
        '''
        execute_write(db, delete_stmt)
        delete_stmt = f'''
            DELETE FROM program_x_levels
                WHERE program_id = {self.id};
        '''
        execute_write(db, delete_stmt)
        delete_stmt = f'''
            DELETE FROM program
                WHERE id = {self.id};
        '''
        execute_write(db, delete_stmt)

    def load_levels(self, db: Any):
        for level_id in self.levels.keys():
            self.levels[level_id] = Level(db = db, id = level_id)

    def add_level(self, db: Any, level_id: int):
        self.levels[level_id] = None
        insert_stmt = f'''
            INSERT INTO program_x_levels (program_id, level_id)
                VALUES ({self.id}, "{level_id}");
        '''
        execute_write(db, insert_stmt)

    def remove_level(self, db: Any, level_id: int):
        self.load_levels(db = db)
        del_level = self.levels.pop(level_id)
        if del_level is not None:
            for level in self.levels.values():
                if level.list_index > del_level.list_index:
                    level.update_basic(list_index = level.list_index - 1)
            del_level.delete()

    def get_next_level_index(self):
        return len(self.levels)+1

    def move_level_index(self, db: Any, level_id: int, new_list_index: int):
        self.load_levels(db = db)
        move_level = self.levels[level_id]
        if move_level is not None and new_list_index != move_level.list_index:
            for level in self.levels.values():
                if new_list_index <= level.list_index < move_level.list_index:
                    level.update_basic(db = db, list_index = level.list_index + 1)
                elif move_level.list_index < level.list_index <= new_list_index:
                    level.update_basic(db = db, list_index = level.list_index - 1)
            move_level.update_basic(list_index = new_list_index)





