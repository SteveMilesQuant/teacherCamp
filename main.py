import os, aiohttp, json, db
from fastapi import FastAPI, Request, APIRouter, Response, status, Form
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from oauthlib.oauth2 import WebApplicationClient
from user import User, load_all_roles, load_all_users_by_role
from student import StudentData, Student
from program import Program, Level, GradeLevel
from camp import Camp, load_camps_table
from datetime import date


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/images", StaticFiles(directory="images"), name="images")
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)
app.user = None
app.db = None
app.db_path = os.environ.get("DB_PATH") or os.path.join(os.path.dirname(__file__), 'app.db')
app.db = db.get_db(app)
app.roles = load_all_roles(db = app.db)
app.instructors = {}
app.promoted_programs = {}
app.camps = {}

templates = Jinja2Templates(directory="templates")
api_router = APIRouter()

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
client = WebApplicationClient(GOOGLE_CLIENT_ID)


async def get_google_provider_cfg() -> dict:
    ret_json = {}
    async with aiohttp.ClientSession() as session:
        async with session.get(GOOGLE_DISCOVERY_URL) as response:
            ret_json = await response.json()
    return ret_json


def build_base_html_args(request: Request) -> dict:
    template_args = {"request": request}
    if app.user is None:
        template_args['user_id'] = None
        template_args['user_name'] = None
        template_args['roles'] = None
    else:
        template_args['user_id'] = app.user.id
        template_args['user_name'] = app.user.full_name
        current_roles = []
        for role_name in app.user.roles:
            current_roles.append(app.roles[role_name])
        template_args['roles'] = current_roles
    return template_args


@api_router.get("/")
async def homepage_get(request: Request):
    template_args = build_base_html_args(request)
    return templates.TemplateResponse("index.html", template_args)


@api_router.get("/signin")
async def signin_get(request: Request):
    google_provider_cfg = await get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    redirect_uri = 'https://' + request.url.netloc + request.url.path + '/callback'
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=redirect_uri,
        scope=["openid", "email", "profile"],
    )
    return RedirectResponse(url=request_uri)


@api_router.get("/signin/callback")
async def signin_callback_get(request: Request, code):
    google_provider_cfg = await get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]
    redirect_url = 'https://' + request.url.netloc + request.url.path
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=f'{request.url}',
        redirect_url=redirect_url,
        code=code,
        client_secret=GOOGLE_CLIENT_SECRET
    )
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(token_url, data=body) as response:
            token_response_json = await response.json()
    client.parse_request_body_response(json.dumps(token_response_json))
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(uri, data=body) as response:
            user_info_json = await response.json()
    if user_info_json.get("email_verified"):
        app.user = User(
            db = app.db,
            google_id = user_info_json["sub"],
            given_name = user_info_json["given_name"],
            family_name = user_info_json["family_name"],
            full_name = user_info_json["name"],
            picture = user_info_json["picture"]
        )
        app.user.add_email_address(db = app.db, email_address = user_info_json["email"])
    else:
        return "User email not available or not verified by Google.", 400
    return RedirectResponse(url='/')


@api_router.get("/signout")
async def signout_get(request: Request):
    app.user = None
    return RedirectResponse(url='/')


@app.on_event("shutdown")
async def shutdown() -> None:
    db.close_db(app)
    if os.environ.get("DEV_MODE") and os.path.isfile(app.db_path):
        os.remove(app.db_path)


def check_basic_auth(permission_url_path, response: Response):
    if not app.user:
        return RedirectResponse(url='/')

    for role_name in app.user.roles:
        role = app.roles[role_name]
        if permission_url_path in role.permissible_endpoints:
            return None

    response.status_code = status.HTTP_403_FORBIDDEN
    return f"User does not have permission for {permission_url_path}"


@api_router.get("/profile")
async def profile_get(request: Request):
    template_args = build_base_html_args(request)
    return templates.TemplateResponse("profile.html", template_args)


@api_router.get("/camps")
async def camps_get(request: Request):
    template_args = build_base_html_args(request)
    return templates.TemplateResponse("camps.html", template_args)


@api_router.get("/students")
async def get_students_page(request: Request, response: Response):
    auth_check = check_basic_auth('/students', response)
    if auth_check is not None:
        return auth_check
    template_args = build_base_html_args(request)
    student_names = {}
    if app.user is not None:
        app.user.load_students(db = app.db)
        for student_id, student in app.user.students.items():
            student_names[student_id] = student.name
    template_args['student_names'] = student_names
    return templates.TemplateResponse("students.html", template_args)

@api_router.get("/students/{student_id}", response_model=StudentData)
async def get_one_student(student_id: int, response: Response):
    if check_basic_auth('/students', response) is not None:
        return StudentData()
    student = app.user.students.get(student_id)
    if student is None:
        response.status_code = status.HTTP_403_FORBIDDEN
        return StudentData()
    return student

@api_router.put("/students/{student_id}", response_model = StudentData)
async def put_update_student(student_id: int, updated_student: StudentData, response: Response):
    if check_basic_auth('/students', response) is not None:
        return StudentData()
    student = app.user.students.get(student_id)
    if student is None:
        response.status_code = status.HTTP_403_FORBIDDEN
        return StudentData()
    student = student.copy(update=updated_student.dict())
    await student.update_basic(app.db)
    app.user.students[student_id] = student
    return student

@api_router.post("/students", response_model = StudentData)
async def post_new_student(new_student_data: StudentData, response: Response):
    if check_basic_auth('/students', response) is not None:
        return StudentData()
    # TODO: there's got to be a slicker way to do this
    new_student = Student(
        db = app.db,
        id = None,
        name = new_student_data.name,
        birthdate = new_student_data.birthdate,
        grade_level = new_student_data.grade_level
    )
    app.user.add_student(db = app.db, student = new_student)
    return new_student

@api_router.delete("/students/{student_id}")
async def delete_student(student_id: int, response: Response):
    if check_basic_auth('/students', response) is not None:
        return None
    app.user.remove_student(db = app.db, student_id = student_id)


@api_router.get("/teach")
async def programs_teach_get(request: Request):
    template_args = build_base_html_args(request)
    return templates.TemplateResponse("teach.html", template_args)


async def programs_get(request: Request):
    template_args = build_base_html_args(request)
    filtertable = None
    if app.user is not None:
        filtertable = app.user.load_programs_table(db = app.db)
    template_args['filtertable'] = filtertable
    return templates.TemplateResponse("programs.html", template_args)


@api_router.get("/programs")
async def programs_get_all(request: Request):
    return await programs_get(request)


async def programs_get_one(request: Request, program_id: int, level_id = None):
    template_args = build_base_html_args(request)
    current_program = None
    current_level = None
    sorted_levels = None
    if app.user is not None:
        if program_id not in app.user.program_ids:
            return RedirectResponse(url='/programs')
        current_program = Program(db = app.db, id = program_id)
        current_program.load_levels(db = app.db)
        sorted_levels = [None] * len(current_program.levels)
        for level in current_program.levels.values():
            sorted_levels[level.list_index-1] = level
    if current_program is not None and level_id is not None:
        current_level = current_program.levels.get(level_id)
    template_args['current_program'] = current_program
    template_args['current_level']  = current_level
    template_args['sorted_levels']  = sorted_levels
    return templates.TemplateResponse("program.html", template_args)


@api_router.get("/programs/{program_id}")
async def programs_get_one_nolevel(request: Request, program_id: int):
    return await programs_get_one(request, program_id, level_id=None)


@api_router.get("/programs/{program_id}/{level_id}")
async def programs_get_one_withlevel(request: Request, program_id: int, level_id: int):
    return await programs_get_one(request, program_id, level_id)


@api_router.post("/programs")
async def programs_post_new(request: Request, title: str = Form(), from_grade: int = Form(), to_grade: int = Form()):
    form = await request.form()
    new_program = Program(
        db = app.db,
        title = title,
        grade_range = (GradeLevel(from_grade), GradeLevel(to_grade)),
        tags = form.get('tags')
    )
    app.user.add_program(db = app.db, program_id = new_program.id)
    return await programs_get_one(request, new_program.id, level_id=None)


@api_router.post("/programs/{program_id}")
async def program_post_update(request: Request, program_id: int):
    level_id = None
    if program_id in app.user.program_ids:
        program = Program(db = app.db, id = program_id)
        form = await request.form()
        level_title = form.get('level_title')
        if level_title is None:
            # Updating a program
            program.update_basic(
                db = app.db,
                title = form.get('program_title'),
                tags = form.get('program_tags'),
                from_grade = form.get('program_from_grade'),
                to_grade = form.get('program_to_grade'),
                description = form.get('program_desc')
            )
        else:
            # New level
            new_level = Level(
                db = app.db,
                title = level_title,
                description = form.get('level_desc'),
                list_index = program.get_next_level_index()
            )
            program.add_level(db = app.db, level_id = new_level.id)
            level_id = new_level.id
    return await programs_get_one(request, program_id, level_id=level_id)


@api_router.post("/programs/{program_id}/{level_id}")
async def level_post_update(request: Request, program_id: int, level_id: int):
    if program_id in app.user.program_ids:
        program = Program(db = app.db, id = program_id)
        program.load_levels(db = app.db)
        level = program.levels.get(level_id)
        if level is not None:
            form = await request.form()
            level.update_basic(
                db = app.db,
                title = form.get('level_title'),
                description = form.get('level_desc')
            )
            level_list_index = form.get('level_list_index')
            if level_list_index is not None:
                program.move_level_index(db = app.db, level_id = level_id, new_list_index = int(level_list_index))
    return await programs_get_one(request, program_id, level_id)


@api_router.delete("/programs/{program_id}")
async def program_delete(request: Request, program_id: int):
    app.user.remove_program(db = app.db, program_id = program_id)


@api_router.delete("/programs/{program_id}/{level_id}")
async def level_delete(request: Request, program_id: int, level_id: int):
    if program_id in app.user.program_ids:
        program = Program(db = app.db, id = program_id)
        program.remove_level(db = app.db, level_id = level_id)


@api_router.get("/members")
async def members_get(request: Request):
    template_args = build_base_html_args(request)
    return templates.TemplateResponse("members.html", template_args)


@api_router.get("/database")
async def database_get(request: Request):
    template_args = build_base_html_args(request)
    return templates.TemplateResponse("database.html", template_args)


async def schedule_get_all_camps(request: Request, template_args: dict):
    user_program_titles = app.user.load_program_titles(db = app.db)
    load_all_users_by_role(db = app.db, role="INSTRUCTOR", users = app.instructors)
    template_args['filtertable'] = load_camps_table(db = app.db)
    template_args['promoted_programs'] = app.promoted_programs
    template_args['user_program_titles'] = user_program_titles
    template_args['instructors'] = app.instructors
    return templates.TemplateResponse("schedule.html", template_args)


@api_router.get("/schedule")
async def schedule_get(request: Request):
    template_args = build_base_html_args(request)
    return await schedule_get_all_camps(request, template_args)


@api_router.post("/schedule")
async def schedule_post_new_camp(request: Request, camp_program_id: int = Form(), camp_instructor_id: int = Form()):
    template_args = build_base_html_args(request)
    new_camp = Camp(db = app.db, program_id = camp_program_id)
    new_camp.add_instructor(db = app.db, user_id = camp_instructor_id)
    return await schedule_get_all_camps(request, template_args)


@api_router.delete("/schedule/{camp_id}")
async def camp_delete(request: Request, camp_id: int):
    load_all_camps(db = app.db, camps = app.camps)
    camp = app.camps.pop(camp_id)
    if camp is not None:
        camp.delete(db = app.db)


@api_router.get("/instructor/{user_id}")
async def instructor_get_one(request: Request, user_id: int):
    template_args = build_base_html_args(request)
    return templates.TemplateResponse("instructor.html", template_args)


app.include_router(api_router)
