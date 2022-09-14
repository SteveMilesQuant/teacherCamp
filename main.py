import os, aiohttp
from fastapi import FastAPI, Request, APIRouter
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from oauthlib.oauth2 import WebApplicationClient


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/images", StaticFiles(directory="images"), name="images")
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)
templates = Jinja2Templates(directory="templates")
api_router = APIRouter()


app.user_display_name = None

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
client = WebApplicationClient(GOOGLE_CLIENT_ID)

async def get_google_provider_cfg():
    ret_json = {}
    async with aiohttp.ClientSession() as session:
        async with session.get(GOOGLE_DISCOVERY_URL) as response:
            ret_json = await response.json()
    return ret_json


@api_router.get("/", status_code = 200)
async def homepage_get(request: Request):
    template_args = {"request": request}
    template_args['user_display_name'] = app.user_display_name
    return templates.TemplateResponse("index.html", template_args)


@api_router.get("/signin")
async def signin_get(request: Request):
    google_provider_cfg = await get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=f'{request.url}' + "/callback",
        scope=["openid", "email", "profile"],
    )
    app.user_display_name = "Uncle Steve"
    return RedirectResponse(url=request_uri)


@api_router.get("/signin/callback")
async def signin_callback_get(request: Request):
    #google_provider_cfg = get_google_provider_cfg(request)
    #code = request.args.get("code")
    #token_endpoint = google_provider_cfg["token_endpoint"]
    app.user_display_name = "Uncle Beep"
    return RedirectResponse(url='/')


@api_router.get("/signout")
async def signin_get(request: Request):
    app.user_display_name = None
    return RedirectResponse(url='/')


app.include_router(api_router)
