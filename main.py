import os, aiohttp, json, db
from fastapi import FastAPI, Request, APIRouter, Form
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from oauthlib.oauth2 import WebApplicationClient
from user import User, load_all_roles, load_all_users_by_role
from student import Student
from program import Program, Level, GradeLevel
from camp import Camp, load_all_camps
from datetime import date


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/images", StaticFiles(directory="images"), name="images")
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)
app.user = None
app.db = None
app.db_path = os.environ.get("DB_PATH") or os.path.join(os.path.dirname(__file__), 'app.db')
app.db = db.get_db(app)
app.roles = load_all_roles(app.db)
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


async def build_base_html_args(request: Request) -> dict:
    template_args = {"request": request}
    if app.user is None:
        template_args['user_id'] = None
        template_args['user_name'] = None
        template_args['roles'] = None
        template_args['grade_levels'] = None
    else:
        template_args['user_id'] = app.user.id
        template_args['user_name'] = app.user.full_name
        current_roles = []
        for role_name in app.user.roles:
            current_roles.append(app.roles[role_name])
        template_args['roles'] = current_roles
        template_args['grade_levels'] = GradeLevel
    return template_args


@api_router.get("/")
async def homepage_get(request: Request):
    template_args = await build_base_html_args(request)
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
            google_id = user_info_json["sub"],
            given_name = user_info_json["given_name"],
            family_name = user_info_json["family_name"],
            full_name = user_info_json["name"],
            google_email = user_info_json["email"],
            picture = user_info_json["picture"],
            db = app.db
        )
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


def check_auth(request: Request, permission_url_path = None):
    if not app.user:
        return templates.TemplateResponse('login.html', template_args)
    if permission_url_path is None:
        permission_url_path = request.url.path
    for role_name in app.user.roles:
        role = app.roles[role_name]
        if permission_url_path in role.permissible_endpoints:
            return None
    return f"User does not have permission for {request.url.path}", 400


@api_router.get("/profile")
async def profile_get(request: Request):
    if not app.user:
        return templates.TemplateResponse('login.html', template_args)
    template_args = await build_base_html_args(request)
    return templates.TemplateResponse("profile.html", template_args)


@api_router.get("/camps")
async def camps_get(request: Request):
    auth_response = check_auth(request, permission_url_path='/camps')
    if auth_response is not None:
        return auth_response
    template_args = await build_base_html_args(request)
    return templates.TemplateResponse("camps.html", template_args)


async def students_get(request: Request, selected_id = None):
    template_args = await build_base_html_args(request)
    student_names = {}
    current_student = None
    if app.user is not None:
        app.user.load_students()
        student = app.user.students.get(selected_id)
        if student is not None:
            current_student = student.deepcopy()
        for student_id, student in app.user.students.items():
            student_names[student_id] = student.name
    template_args['student_names'] = student_names
    template_args['current_student'] = current_student
    return templates.TemplateResponse("students.html", template_args)


@api_router.get("/students")
async def students_get_all(request: Request):
    auth_response = check_auth(request, permission_url_path='/students')
    if auth_response is not None:
        return auth_response
    return await students_get(request=request, selected_id=None)


@api_router.get("/students/{student_id}")
async def students_get_one(request: Request, student_id: int):
    auth_response = check_auth(request, permission_url_path='/students')
    if auth_response is not None:
        return auth_response
    return await students_get(request=request, selected_id=student_id)


@api_router.post("/students")
async def student_post_new(request: Request, student_name: str = Form(), student_birthdate: date = Form(), student_grade_level: int = Form()):
    auth_response = check_auth(request, permission_url_path='/students')
    if auth_response is not None:
        return auth_response
    app.user.load_students()
    new_student = Student(
        id = None,
        db = app.db,
        name = student_name,
        birthdate = student_birthdate,
        grade_level = GradeLevel(student_grade_level)
    )
    app.user.add_student(new_student.id)
    student_id = new_student.id
    return await students_get(request=request, selected_id=student_id)


@api_router.post("/students/{student_id}")
async def student_post_update(request: Request, student_id: int):
    auth_response = check_auth(request, permission_url_path='/students')
    if auth_response is not None:
        return auth_response
    app.user.load_students()
    student = app.user.students.get(student_id)
    if student is not None:
        form = await request.form()
        student.update_basic(
            name = form.get('student_name'),
            birthdate = form.get('student_birthdate'),
            grade_level = form.get('student_grade_level'),
            school = None # Will do later with Google maps API
        )
    return await students_get(request=request, selected_id=student_id)


@api_router.delete("/students/{student_id}")
async def student_delete(request: Request, student_id: int):
    if check_auth(request, permission_url_path='/students') is None:
        app.user.remove_student(student_id)


@api_router.get("/teach")
async def programs_teach_get(request: Request):
    auth_response = check_auth(request, permission_url_path='/teach')
    if auth_response is not None:
        return auth_response
    template_args = await build_base_html_args(request)
    return templates.TemplateResponse("teach.html", template_args)


async def programs_get(request: Request):
    template_args = await build_base_html_args(request)
    programs = {}
    if app.user is not None:
        app.user.load_programs()
        for program in app.user.programs.values():
            programs[program.id] = program.deepcopy()
    template_args['programs'] = programs
    return templates.TemplateResponse("programs.html", template_args)


@api_router.get("/programs")
async def programs_get_all(request: Request):
    auth_response = check_auth(request, permission_url_path='/programs')
    if auth_response is not None:
        return auth_response
    return await programs_get(request)


async def programs_get_one(request: Request, program_id: int, level_id = None):
    template_args = await build_base_html_args(request)
    current_program = None
    current_level = None
    sorted_levels = None
    if app.user is not None:
        app.user.load_programs()
        program = app.user.programs.get(program_id)
        if program is None:
            return RedirectResponse(url='/programs')
        program.load_levels()
        current_program = program.deepcopy()
        sorted_levels = [None] * len(current_program.levels)
        for level in current_program.levels.values():
            sorted_levels[level.list_index-1] = level
    if current_program is not None and level_id is not None:
        level = current_program.levels.get(level_id)
        if level is not None:
            current_level = level.deepcopy()
    template_args['current_program'] = current_program
    template_args['current_level']  = current_level
    template_args['sorted_levels']  = sorted_levels
    return templates.TemplateResponse("program.html", template_args)


@api_router.get("/programs/{program_id}")
async def programs_get_one_nolevel(request: Request, program_id: int):
    auth_response = check_auth(request, permission_url_path='/programs')
    if auth_response is not None:
        return auth_response
    return await programs_get_one(request, program_id, level_id=None)


@api_router.get("/programs/{program_id}/{level_id}")
async def programs_get_one_withlevel(request: Request, program_id: int, level_id: int):
    auth_response = check_auth(request, permission_url_path='/programs')
    if auth_response is not None:
        return auth_response
    return await programs_get_one(request, program_id, level_id)


@api_router.post("/programs")
async def programs_post_new(request: Request, title: str = Form(), from_grade: int = Form(), to_grade: int = Form()):
    auth_response = check_auth(request, permission_url_path='/programs')
    if auth_response is not None:
        return auth_response
    form = await request.form()
    new_program = Program(
        db = app.db,
        title = title,
        grade_range = (GradeLevel(from_grade), GradeLevel(to_grade)),
        tags = form.get('tags')
    )
    app.user.add_program(new_program.id)
    return await programs_get_one(request, new_program.id, level_id=None)


@api_router.post("/programs/{program_id}")
async def program_post_update(request: Request, program_id: int):
    auth_response = check_auth(request, permission_url_path='/programs')
    if auth_response is not None:
        return auth_response
    app.user.load_programs()
    program = app.user.programs.get(program_id)
    level_id = None
    if program is not None:
        form = await request.form()
        level_title = form.get('level_title')
        if level_title is None:
            # Updating a program
            program.update_basic(
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
            program.add_level(new_level.id)
            level_id = new_level.id
    return await programs_get_one(request, program_id, level_id=level_id)


@api_router.post("/programs/{program_id}/{level_id}")
async def level_post_update(request: Request, program_id: int, level_id: int):
    auth_response = check_auth(request, permission_url_path='/programs')
    if auth_response is not None:
        return auth_response
    app.user.load_programs()
    program = app.user.programs.get(program_id)
    if program is not None:
        program.load_levels()
        level = program.levels.get(level_id)
        if level is not None:
            form = await request.form()
            level.update_basic(
                title = form.get('level_title'),
                description = form.get('level_desc')
            )
            level_list_index = form.get('level_list_index')
            if level_list_index is not None:
                program.move_level_index(level_id, int(level_list_index))
    return await programs_get_one(request, program_id, level_id)


@api_router.delete("/programs/{program_id}")
async def program_delete(request: Request, program_id: int):
    if check_auth(request, permission_url_path='/programs') is None:
        app.user.remove_program(program_id)


@api_router.delete("/programs/{program_id}/{level_id}")
async def level_delete(request: Request, program_id: int, level_id: int):
    if check_auth(request, permission_url_path='/programs') is None:
        app.user.load_programs()
        program = app.user.programs.get(program_id)
        if program is not None:
            program.remove_level(level_id)


@api_router.get("/members")
async def members_get(request: Request):
    auth_response = check_auth(request, permission_url_path='/members')
    if auth_response is not None:
        return auth_response
    template_args = await build_base_html_args(request)
    return templates.TemplateResponse("members.html", template_args)


@api_router.get("/database")
async def database_get(request: Request):
    auth_response = check_auth(request, permission_url_path='/database')
    if auth_response is not None:
        return auth_response
    template_args = await build_base_html_args(request)
    return templates.TemplateResponse("database.html", template_args)


async def schedule_get_all_camps(request: Request, template_args: dict):
    load_all_camps(app.db, app.camps, force_load=True)
    app.user.load_programs()
    user_programs = {}
    for program in app.user.programs.values():
        user_programs[program.id] = program.deepcopy()
    load_all_users_by_role(app.db, app.instructors, role="INSTRUCTOR", force_load=True)
    template_args['camps'] = app.camps
    template_args['promoted_programs'] = app.promoted_programs
    template_args['user_programs'] = user_programs
    template_args['instructors'] = app.instructors
    return templates.TemplateResponse("schedule.html", template_args)


@api_router.get("/schedule")
async def schedule_get(request: Request):
    auth_response = check_auth(request, permission_url_path='/schedule')
    if auth_response is not None:
        return auth_response
    template_args = await build_base_html_args(request)
    return await schedule_get_all_camps(request, template_args)


@api_router.post("/schedule")
async def schedule_post_new_camp(request: Request, camp_program_id: int = Form(), camp_instructor_id: int = Form()):
    auth_response = check_auth(request, permission_url_path='/schedule')
    if auth_response is not None:
        return auth_response
    template_args = await build_base_html_args(request)
    load_all_camps(app.db, app.camps)
    new_camp = Camp(db = app.db, program_id = camp_program_id)
    new_camp.add_instructor(camp_instructor_id)
    new_camp.db = None
    return await schedule_get_all_camps(request, template_args)


@api_router.delete("/schedule/{camp_id}")
async def camp_delete(request: Request, camp_id: int):
    if check_auth(request, permission_url_path='/schedule') is None:
        load_all_camps(app.db, app.camps)
        camp = app.camps.pop(camp_id)
        if camp is not None:
            camp.db = app.db
            camp.delete()


@api_router.get("/instructor/{user_id}")
async def instructor_get_one(request: Request, user_id: int):
    auth_response = check_auth(request, permission_url_path='/camps') # a user that has permission to camps should be able to see instructors
    if auth_response is not None:
        return auth_response
    template_args = await build_base_html_args(request)
    return templates.TemplateResponse("instructor.html", template_args)


app.include_router(api_router)
