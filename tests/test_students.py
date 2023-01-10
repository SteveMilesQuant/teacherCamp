import os
from fastapi import status
from fastapi.testclient import TestClient

db_path = './tests/test_students.db'
if os.path.isfile(db_path):
    os.remove(db_path)
os.environ['DB_PATH'] = db_path
from main import app

client = TestClient(app)

def test_read_students():
    response = client.get('/')
    assert response.status_code == status.HTTP_200_OK




def test_clean_up():
    os.remove(db_path)

