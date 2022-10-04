import os, aiohttp, json, db
from fastapi import FastAPI, Request, APIRouter, Form
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from oauthlib.oauth2 import WebApplicationClient
from user import User, load_all_roles
from student import Student
from program import Program, Level, GradeLevel
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


def check_auth(request: Request, permission_url_path = None) -> bool:
    if app.user:
        if permission_url_path is None:
            permission_url_path = request.url.path
        for role_name in app.user.roles:
            role = app.roles[role_name]
            if permission_url_path in role.permissible_endpoints:
                return True
    return False


def resolve_auth_endpoint(request: Request, tgt_html: str, template_args: dict, permission_url_path = None):
    if not app.user:
        return templates.TemplateResponse('login.html', template_args)
    if permission_url_path is None:
        permission_url_path = request.url.path
    for role_name in app.user.roles:
        role = app.roles[role_name]
        if permission_url_path in role.permissible_endpoints:
            return templates.TemplateResponse(tgt_html, template_args)
    return f"User does not have permission for {request.url.path}", 400


@api_router.get("/profile")
async def profile_get(request: Request):
    if not app.user:
        return templates.TemplateResponse('login.html', template_args)
    template_args = await build_base_html_args(request)
    return templates.TemplateResponse("profile.html", template_args)


@api_router.get("/camps")
async def camps_get(request: Request):
    template_args = await build_base_html_args(request)
    return resolve_auth_endpoint(request, "camps.html", template_args)


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
    return resolve_auth_endpoint(request, "students.html", template_args, permission_url_path='/students')


@api_router.get("/students")
async def students_get_all(request: Request):
    return await students_get(request=request, selected_id=None)


@api_router.get("/students/{student_id}")
async def students_get_one(request: Request, student_id: int):
    return await students_get(request=request, selected_id=student_id)


@api_router.post("/students")
async def student_post_new(request: Request, student_name: str = Form(), student_birthdate: date = Form()):
    if not check_auth(request):
        template_args = await build_base_html_args(request)
        return resolve_auth_endpoint(request, "students.html", template_args)
    app.user.load_students()
    new_student = Student(
        id = None,
        db = app.db,
        name = student_name,
        birthdate = student_birthdate
    )
    app.user.students[new_student.id] = new_student
    student_id = new_student.id
    app.user.update()
    return await students_get(request=request, selected_id=student_id)


@api_router.post("/students/{student_id}")
async def student_post_update(request: Request, student_id: int):
    if not check_auth(request, permission_url_path='/students'):
        template_args = await build_base_html_args(request)
        return resolve_auth_endpoint(request, "students.html", template_args)
    app.user.load_students()
    student = app.user.students.get(student_id)
    if student is not None:
        form = await request.form()
        student.update_basic(
            name = form.get('student_name'),
            birthdate_str = form.get('student_birthdate'),
            school = None # Will do later with Google maps API
        )
    return await students_get(request=request, selected_id=student_id)


@api_router.delete("/students/{student_id}")
async def student_delete(request: Request, student_id: int):
    if check_auth(request, permission_url_path='/students'):
        app.user.remove_student(student_id)


@api_router.get("/teach")
async def programs_teach_get(request: Request):
    template_args = await build_base_html_args(request)
    return resolve_auth_endpoint(request, "teach.html", template_args)


async def programs_get(request: Request):
    template_args = await build_base_html_args(request)
    programs = {}
    if app.user is not None:
        app.user.load_programs()
        for program in app.user.programs.values():
            programs[program.id] = program.deepcopy()
    template_args['programs'] = programs
    return resolve_auth_endpoint(request, "programs.html", template_args, permission_url_path='/programs')


@api_router.get("/programs")
async def programs_get_all(request: Request):
    return await programs_get(request)


async def programs_get_one(request: Request, program_id: int, level_id = None):
    template_args = await build_base_html_args(request)
    current_program = None
    current_level = None
    if app.user is not None:
        program = app.user.programs.get(program_id)
        if program is None:
            return RedirectResponse(url='/programs')
        program.load_levels()
        current_program = program.deepcopy()
    if current_program is not None and level_id is not None:
        level = current_program.levels.get(level_id)
        if level is not None:
            current_level = level.deepcopy()
    template_args['current_program'] = current_program
    template_args['current_level']  = current_level
    return resolve_auth_endpoint(request, "program.html", template_args, permission_url_path='/programs')


@api_router.get("/programs/{program_id}")
async def programs_get_one_nolevel(request: Request, program_id: int):
    return await programs_get_one(request, program_id, level_id=None)


@api_router.get("/programs/{program_id}/{level_id}")
async def programs_get_one_withlevel(request: Request, program_id: int, level_id: int):
    return await programs_get_one(request, program_id, level_id)


@api_router.post("/programs")
async def programs_post_new(request: Request, title: str = Form(), from_grade: int = Form(), to_grade: int = Form()):
    if not check_auth(request):
        template_args = await build_base_html_args(request)
        return resolve_auth_endpoint(request, "programs.html", template_args)
    form = await request.form()
    tags = form.get('tags')
    if tags is not None:
        tags = tags.lower()
    new_program = Program(
        db = app.db,
        title = title,
        grade_range = (GradeLevel(from_grade), GradeLevel(to_grade)),
        tags = tags
    )
    app.user.load_programs()
    app.user.programs[new_program.id] = new_program
    app.user.update()
    return await programs_get_one(request, new_program.id, level_id=None)


@api_router.post("/programs/{program_id}")
async def program_post_update(request: Request, program_id: int):
    if not check_auth(request, permission_url_path='/programs'):
        template_args = await build_base_html_args(request)
        return resolve_auth_endpoint(request, "programs.html", template_args, permission_url_path='/programs')
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
            program.add_level(new_level)
            level_id = new_level.id
    return await programs_get_one(request, program_id, level_id=level_id)


@api_router.post("/programs/{program_id}/{level_id}")
async def level_post_update(request: Request, program_id: int, level_id: int):
    if not check_auth(request, permission_url_path='/programs'):
        template_args = await build_base_html_args(request)
        return resolve_auth_endpoint(request, "programs.html", template_args, permission_url_path='/programs')
    program = app.user.programs.get(program_id)
    if program is not None:
        program.load_levels()
        level = program.levels.get(level_id)
        if level is not None:
            form = await request.form()
            level.update_basic(
                list_of_levels = program.levels,
                title = form.get('level_title'),
                description = form.get('level_desc'),
                list_index = form.get('level_list_index')
            )
    return await programs_get_one(request, program_id, level_id)


@api_router.delete("/programs/{program_id}")
async def program_delete(request: Request, program_id: int):
    if check_auth(request, permission_url_path='/programs'):
        app.user.remove_program(program_id)


@api_router.delete("/programs/{program_id}/{level_id}")
async def level_delete(request: Request, program_id: int, level_id: int):
    if check_auth(request, permission_url_path='/programs'):
        program = app.user.programs.get(program_id)
        if program is not None:
            program.remove_level(level_id)


@api_router.get("/members")
async def members_get(request: Request):
    template_args = await build_base_html_args(request)
    return resolve_auth_endpoint(request, "members.html", template_args)


@api_router.get("/database")
async def database_get(request: Request):
    template_args = await build_base_html_args(request)
    return resolve_auth_endpoint(request, "database.html", template_args)


@api_router.get("/schedule")
async def schedule_get(request: Request):
    template_args = await build_base_html_args(request)
    return resolve_auth_endpoint(request, "schedule.html", template_args)


@api_router.get("/instructor/{user_id}")
async def instructor_get_one(request: Request, user_id: int):
    template_args = await build_base_html_args(request)
    return resolve_auth_endpoint(
        request, "instructor.html",
        template_args,
        permission_url_path='/camps' # a user that has permission to camps should be able to see instructors
    )


app.include_router(api_router)
