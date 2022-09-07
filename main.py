from fastapi import FastAPI, Request, APIRouter
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/images", StaticFiles(directory="images"), name="images")
templates = Jinja2Templates(directory="templates")
api_router = APIRouter()


@api_router.get("/", status_code = 200)
async def read_homepage(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})


@api_router.get("/login", status_code = 200)
async def read_login(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})


@api_router.get("/register", status_code = 200)
async def read_register(request: Request):
    return templates.TemplateResponse("auth/register.html", {"request": request})


app.include_router(api_router)
