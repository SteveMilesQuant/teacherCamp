import sqlite3, os
from fastapi import FastAPI
from urllib.request import pathname2url
from user import User


def get_db(app: FastAPI):
    if app.db is None:
        try:
            app.db = sqlite3.connect('file:{}?mode=rw'.format(pathname2url(app.db_path)))
        except sqlite3.OperationalError:
            app.db = sqlite3.connect(app.db_path)
            with open(os.path.join(os.path.dirname(__file__), 'schema.sql'), encoding='utf-8') as schema_file:
                app.db.executescript(schema_file.read())
                app.db.commit()
    return app.db


def close_db(app: FastAPI):
    if app.db is not None:
        app.db.close()
    app.db = None


def load_user(db: sqlite3.Connection, user_id: int):
    user = None
    cursor = db.execute(f'SELECT id, given_name, family_name, full_name, primary_email, picture FROM user WHERE id = {user_id}')
    row = cursor.fetchone()
    if row is not None:
        user = User(
            id = row[0],
            given_name = row[1],
            family_name = row[2],
            full_name = row[3],
            primary_email = row[4],
            picture = row[5]
        )
    return user


def save_user(db: sqlite3.Connection, user: User) -> None:
    sql_string = f'''
        INSERT INTO user (id, given_name, family_name, full_name, primary_email, picture)
            VALUES ({user.id}, "{user.given_name}", "{user.family_name}", "{user.full_name}", "{user.primary_email}", "{user.picture}");
    '''
    db.execute(sql_string)
    db.commit()

