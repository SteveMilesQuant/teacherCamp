from fastapi import FastAPI, Request, APIRouter
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/images", StaticFiles(directory="images"), name="images")
templates = Jinja2Templates(directory="templates")
api_router = APIRouter()

def get_login_menu():
    return {"login": "Log In"}

@api_router.get("/", status_code = 200)
async def read_homepage(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "login_menu": get_login_menu()})


@api_router.get("/login", status_code = 200)
async def read_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "login_menu": get_login_menu()})



app.include_router(api_router)
