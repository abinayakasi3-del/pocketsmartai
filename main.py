"""PocketSmart AI - FastAPI backend. Run: uvicorn main:app --reload"""
import os, json, time, hashlib, secrets
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
import gemini_utils as ai

load_dotenv()
app = FastAPI(title="PocketSmart AI")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "dev-secret"))
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
templates = Jinja2Templates(directory="templates")
DB = Path("data.json")

PLANNERS = {
    "home": {"title": "Home interior planner", "fields": [
        ("budget", "Total budget (₹)", "number", None), ("rooms", "Rooms (e.g. Living Room, Kitchen)", "text", None),
        ("lights", "Lights", "number", None), ("fans", "Ceiling fans", "number", None),
        ("tables", "Dining tables", "number", None),
        ("style", "Style", "select", ["Modern", "Minimal", "Traditional", "Scandinavian"])]},
    "party": {"title": "Party planner", "fields": [
        ("budget", "Total budget (₹)", "number", None), ("guests", "Guests", "number", None),
        ("event_type", "Event", "select", ["Birthday", "Corporate", "Wedding", "Get-together"]),
        ("venue", "Venue / stay needs", "text", None)]},
    "jewelry": {"title": "Jewelry planner", "fields": [
        ("budget", "Total budget (₹)", "number", None),
        ("occasion", "Occasion", "select", ["Wedding", "Festival", "Office", "Party"]),
        ("style", "Style", "select", ["Traditional", "Modern", "Minimal", "Statement"]),
        ("outfit", "Outfit photo (optional)", "file", None)]},
}


def load():
    return json.loads(DB.read_text()) if DB.exists() else {"users": {}, "history": {}}

def save(d):
    DB.write_text(json.dumps(d, indent=1))

def hash_pw(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 100_000).hex()

def user(request):
    return request.session.get("user")

def render(request, name, **ctx):
    return templates.TemplateResponse(request, name, {"user": user(request), **ctx})


@app.get("/")
async def index(request: Request):
    return render(request, "index.html", planners=PLANNERS)

@app.get("/register")
async def register_page(request: Request):
    return render(request, "auth.html", mode="register", error=None)

@app.post("/register")
async def register(request: Request, username: str = Form(...), password: str = Form(...)):
    db, username = load(), username.strip().lower()
    if len(username) < 3 or len(password) < 6:
        return render(request, "auth.html", mode="register", error="Username needs 3+ characters and password 6+.")
    if username in db["users"]:
        return render(request, "auth.html", mode="register", error="That username is taken.")
    salt = secrets.token_hex(8)
    db["users"][username] = {"salt": salt, "hash": hash_pw(password, salt)}
    save(db)
    request.session["user"] = username
    return RedirectResponse("/", 303)

@app.get("/login")
async def login_page(request: Request):
    return render(request, "auth.html", mode="login", error=None)

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    u = load()["users"].get(username.strip().lower())
    if not u or hash_pw(password, u["salt"]) != u["hash"]:
        return render(request, "auth.html", mode="login", error="Wrong username or password.")
    request.session["user"] = username.strip().lower()
    return RedirectResponse("/", 303)

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", 303)

@app.get("/planner/{kind}")
async def planner(request: Request, kind: str):
    if kind not in PLANNERS:
        return RedirectResponse("/", 303)
    if not user(request):
        return RedirectResponse("/login", 303)
    return render(request, "planner.html", kind=kind, p=PLANNERS[kind])

async def generate(request: Request, kind: str):
    if not user(request):
        return JSONResponse({"error": "Please log in first."}, 401)
    form = await request.form()
    data = {k: v for k, v in form.items() if isinstance(v, str) and v}
    try:
        budget = int(float(data.get("budget", 0)))
        assert budget > 0
    except Exception:
        return JSONResponse({"error": "Enter a budget greater than 0."}, 422)
    f, image = form.get("outfit"), None
    if f is not None and getattr(f, "filename", ""):
        image = (await f.read(), f.content_type)
    result = ai.recommend(kind, data, budget, image)
    db = load()
    db["history"].setdefault(user(request), []).insert(0, {"time": time.strftime("%d %b %Y, %H:%M"),
                                                         "kind": kind, "budget": budget, "result": result})
    save(db)
    return result

@app.post("/generate-home")
async def generate_home(request: Request):
    return await generate(request, "home")

@app.post("/generate-party")
async def generate_party(request: Request):
    return await generate(request, "party")

@app.post("/generate-jewelry")
async def generate_jewelry(request: Request):
    return await generate(request, "jewelry")

@app.get("/history")
async def history(request: Request):
    if not user(request):
        return RedirectResponse("/login", 303)
    return render(request, "history.html", items=load()["history"].get(user(request), []))

@app.get("/session-info")
async def session_info(request: Request):
    return {"logged_in": bool(user(request)), "user": user(request)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
