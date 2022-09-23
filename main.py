import os, aiohttp, json, db
from fastapi import FastAPI, Request, APIRouter, Form
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from oauthlib.oauth2 import WebApplicationClient
from user import User, load_all_roles, Student


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
            id = user_info_json["sub"],
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


@api_router.get("/programs/find")
async def programs_find_get(request: Request):
    template_args = await build_base_html_args(request)
    return resolve_auth_endpoint(request, "find_programs.html", template_args)


@api_router.get("/programs/enrolled")
async def programs_enrolled_get(request: Request):
    template_args = await build_base_html_args(request)
    return resolve_auth_endpoint(request, "enrolled_programs.html", template_args)


async def students_get(request: Request, selected_id = None):
    template_args = await build_base_html_args(request)
    student_names = {}
    current_student = None

    if app.user is not None:
        if selected_id is not None:
            if selected_id in app.user.student_ids:
                current_student = Student(db = app.db, id = selected_id)
        for student_id in app.user.student_ids:
            student_names[student_id] = Student(db = app.db, id = student_id).name # this is readable, but maybe it should be more efficient
    template_args['student_names'] = student_names
    template_args['current_student'] = current_student
    return resolve_auth_endpoint(request, "students.html", template_args, permission_url_path='/students')

async def student_add_or_update(student_id = None, student_name = ""):
    if app.user is not None:
        student = Student(db = app.db, id = student_id, name = student_name)
        if student_id is not None:
            student.name = student_name
            student.update()
        if student.id not in app.user.student_ids:
            app.user.student_ids.append(student.id)
            app.user.update()
        return student.id
    return None

@api_router.get("/students")
async def students_get_all(request: Request):
    return await students_get(request=request, selected_id=None)

@api_router.get("/students/{student_id}")
async def students_get_one(request: Request, student_id: int):
    return await students_get(request=request, selected_id=student_id)

@api_router.post("/students")
async def student_post(request: Request, student_name: str = Form()):
    student_id = await student_add_or_update(student_id = None, student_name = student_name)
    return await students_get(request=request, selected_id=student_id)
    
@api_router.post("/students/{student_id}")
async def student_post(request: Request, student_id: int, student_name: str = Form()):
    student_id = await student_add_or_update(student_id = student_id, student_name = student_name)
    return await students_get(request=request, selected_id=student_id)

@api_router.get("/programs/teach")
async def programs_teach_get(request: Request):
    template_args = await build_base_html_args(request)
    return resolve_auth_endpoint(request, "teach_programs.html", template_args)


@api_router.get("/programs/design")
async def programs_design_get(request: Request):
    template_args = await build_base_html_args(request)
    return resolve_auth_endpoint(request, "design_programs.html", template_args)


@api_router.get("/members")
async def members_get(request: Request):
    template_args = await build_base_html_args(request)
    return resolve_auth_endpoint(request, "members.html", template_args)


@api_router.get("/database")
async def database_get(request: Request):
    template_args = await build_base_html_args(request)
    return resolve_auth_endpoint(request, "database.html", template_args)


@api_router.get("/programs/schedule")
async def programs_schedule_get(request: Request):
    template_args = await build_base_html_args(request)
    return resolve_auth_endpoint(request, "program_scheduling.html", template_args)


app.include_router(api_router)
