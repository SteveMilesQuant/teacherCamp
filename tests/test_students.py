import os, pytest, json
from fastapi import status
from fastapi.testclient import TestClient
from user import User
from student import StudentData
from datetime import date

db_path = os.path.join(os.path.dirname(__file__), 'test_students.db')
if os.path.isfile(db_path):
    os.remove(db_path)
os.environ['DB_PATH'] = db_path
from main import app

client = TestClient(app)

all_students_json = {}

# Create test user
app.user = User(
    db = app.db,
    google_id = 1,
    given_name = 'Steve',
    family_name = 'Tester',
    full_name = 'Steve Tester',
    picture = ''
)

# Test webpage read
def test_get_students_html():
    response = client.get('/students')
    assert response.status_code == status.HTTP_200_OK


# Test adding students
@pytest.mark.parametrize(('student'), (
    (StudentData(name='Karen Tester', birthdate=date(1987, 6, 15), grade_level=6)),
    (StudentData(name='Cheri Tester', birthdate=date(1988, 7, 16), grade_level=7)),
    (StudentData(name='Renee Tester', birthdate=date(1989, 8, 17), grade_level=8)),
))
def test_post_students(student: StudentData):
    student_json = json.loads(json.dumps(student.dict(), indent=4, sort_keys=True, default=str))
    response = client.post('/students', json=student_json)
    assert response.status_code == status.HTTP_200_OK, f'Error posting {student_json}'
    new_student_json = response.json()
    student_json['id'] = new_student_json['id']
    assert student_json == new_student_json, f'Returned student {new_student_json} does not match posted student {student_json}.'
    all_students_json[new_student_json['name']] = new_student_json


# Test getting individual students back
def test_get_student():
    for student_json in all_students_json.values():
        response = client.get('/students/' + str(student_json['id']))
        assert response.status_code == status.HTTP_200_OK, f'Error getting {student_json}'
        got_student_json = response.json()
        assert student_json == got_student_json, f'Returned student {got_student_json} does not match requested student {student_json}.'


# Test updating students
@pytest.mark.parametrize(('student'), (
    (StudentData(name='Karen Tester', birthdate=date(1997, 6, 15), grade_level=1)),
    (StudentData(name='Cheri Tester', birthdate=date(1998, 7, 16), grade_level=2)),
    (StudentData(name='Renee Tester', birthdate=date(1999, 8, 17), grade_level=3)),
))
def test_put_student(student: StudentData):
    student.id = all_students_json[student.name]['id']
    student_json = json.loads(json.dumps(student.dict(), indent=4, sort_keys=True, default=str))
    response = client.put('/students/' + str(student.id), json=student_json)
    assert response.status_code == status.HTTP_200_OK, f'Error putting {student_json}'
    new_student_json = response.json()
    assert student_json == new_student_json, f'Returned student {new_student_json} does not match put student {student_json}.'


# Permission test: student not in user's list
def test_student_permission():
    max_student_id = 0
    for student_json in all_students_json.values():
        max_student_id = max(max_student_id, student_json['id'])
    student = StudentData(id=max_student_id + 1, name='Karen Tester', birthdate=date(1997, 6, 15), grade_level=1)
    student_error_json = {'detail': f'User does not have permission for student id={student.id}'}
    response = client.get('/students/' + str(student.id))
    assert response.status_code == status.HTTP_403_FORBIDDEN
    student_json = json.loads(json.dumps(student.dict(), indent=4, sort_keys=True, default=str))
    response = client.put('/students/' + str(student.id), json=student_json)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    returned_json = response.json()
    assert returned_json == student_error_json


# Remove temporary database
def test_clean_up():
    os.remove(db_path)

