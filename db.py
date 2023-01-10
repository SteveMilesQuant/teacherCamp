import sqlite3, os
from fastapi import FastAPI
from urllib.request import pathname2url
from pydantic import BaseModel


class ColumnMeta(BaseModel):
    name: str
    display_html: bool
    display_label: str
    can_filter: bool


def get_db(app: FastAPI):
    if app.db is None:
        try:
            app.db = sqlite3.connect('file:{}?mode=rw'.format(pathname2url(app.db_path)), check_same_thread=False)
        except sqlite3.OperationalError:
            app.db = sqlite3.connect(app.db_path, check_same_thread=False)
            with open(os.path.join(os.path.dirname(__file__), 'schema.sql'), encoding='utf-8') as schema_file:
                app.db.executescript(schema_file.read())
                app.db.commit()
    return app.db


def close_db(app: FastAPI):
    if app.db is not None:
        app.db.close()
    app.db = None


def execute_read(db: sqlite3.Connection, stmt: str):
    cursor = db.execute(stmt)
    cursor.row_factory = sqlite3.Row
    rows = cursor.fetchall()
    if len(rows) > 0:
        return rows
    else:
        return None


def execute_write(db: sqlite3.Connection, stmt: str) -> None:
    cursor = db.execute(stmt)
    db.commit()
    return cursor.lastrowid

