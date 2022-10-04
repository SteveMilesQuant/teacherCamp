import copy
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
    db: Any

    def _load(self) -> bool:
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

    def _create(self):
        insert_stmt = f'''
            INSERT INTO level (title, description, list_index)
                VALUES ("{self.title}", "{self.description}", {self.list_index});
        '''
        self.id = execute_write(self.db, insert_stmt)

    def __init__(self, **data):
        super().__init__(**data)
        if self.id is None:
            self._create()
        elif not self._load():
            self._create()

    def update_basic(self,
            title: Optional[str] = None,
            description: Optional[str] = None,
            list_index: Optional[int] = None,
            list_of_levels: Optional[Dict] = None # Must provide if updating list_index
        ):
        if title is not None:
            self.title = title
        if description is not None:
            self.description = description
        if list_index is not None and list_index != self.list_index:
            assert list_of_levels is not None
            for level in list_of_levels.values():
                if level.id != self.id:
                    do_update = False
                    if list_index <= level.list_index < self.list_index:
                        level.list_index = level.list_index + 1
                        do_update = True
                    elif self.list_index < level.list_index < list_index:
                        level.list_index = level.list_index - 1
                        do_update = True
                    if do_update:
                        update_stmt = f'''
                            UPDATE level
                                SET list_index={level.list_index}
                                WHERE id = {level.id};
                        '''
                        execute_write(self.db, update_stmt)
            self.list_index = list_index
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

    def deepcopy(self):
        save_db = self.db
        self.db = None
        deep_copy = copy.deepcopy(self)
        self.db = save_db
        return deep_copy


class Program(BaseModel):
    id: Optional[int]
    title: Optional[str]
    grade_range: Optional[tuple[GradeLevel,GradeLevel]]
    tags: Optional[str] = ''
    description: Optional[str] = ''
    db: Any
    levels: Optional[Dict[int, Level]] = {}

    def _load(self) -> bool:
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
        self.grade_range = (GradeLevel(row['from_grade']), GradeLevel(row['to_grade']))
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

    def _create(self):
        insert_stmt = f'''
            INSERT INTO program (title, from_grade, to_grade, tags, description)
                VALUES ("{self.title}", {self.grade_range[0].value}, {self.grade_range[1].value}, "{self.tags}", "{self.description}");
        '''
        self.id = execute_write(self.db, insert_stmt)

    def __init__(self, **data):
        super().__init__(**data)
        if self.id is None:
            self._create()
        elif not self._load():
            self._create()

    def update_basic(self,
            title: Optional[str] = None,
            from_grade: Optional[int] = None,
            to_grade: Optional[int] = None,
            tags: Optional[str] = None,
            description: Optional[str] = None
        ):
        if title is not None:
            self.title = title
        if from_grade is not None:
            self.grade_range[0] = GradeLevel(from_grade)
        if to_grade is not None:
            self.grade_range[1] = GradeLevel(to_grade)
        if tags is not None:
            self.tags = tags
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
        execute_write(self.db, update_stmt)

    def delete(self):
        # Levels are not shared across programs, so they are safe to delete when we delete the program
        delete_stmt = f'''
            DELETE FROM user_x_programs
                WHERE program_id = {self.id};
        '''
        execute_write(self.db, delete_stmt)
        delete_stmt = f'''
            DELETE FROM program_x_levels
                WHERE program_id = {self.id};
        '''
        execute_write(self.db, delete_stmt)
        delete_stmt = f'''
            DELETE FROM program
                WHERE id = {self.id};
        '''
        execute_write(self.db, delete_stmt)

    def load_levels(self):
        for level_id in self.levels.keys():
            self.levels[level_id] = Level(id=level_id, db=self.db)

    def add_level(self, level: Level):
        self.levels[level.id] = level
        insert_stmt = f'''
            INSERT INTO program_x_levels (program_id, level_id)
                VALUES ({self.id}, "{level.id}");
        '''
        execute_write(self.db, insert_stmt)

    def remove_level(self, level_id: int):
        self.load_levels()
        del_level = self.levels.pop(level_id)
        if del_level is not None:
            for level in self.levels.values():
                if level.list_index > del_level.list_index:
                    level.update_basic(
                        list_of_levels = self.levels,
                        list_index = level.list_index - 1
                    )
            del_level.delete()

    def get_next_level_index(self):
        self.load_levels()
        next_index = 0
        for level in self.levels.values():
            next_index = max(next_index, level.list_index)
        next_index = next_index + 1
        return next_index

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


