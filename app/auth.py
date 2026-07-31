import os
from urllib.parse import parse_qs, urlparse
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

config = Config(".env")

oauth = OAuth(config)
oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

_serializer = URLSafeTimedSerializer(os.getenv("SESSION_SECRET", "dev-secret-change-me"))

SESSION_COOKIE = "candidate_session"
SESSION_REDIRECT_KEY = "post_auth_redirect"
# SESSION_MAX_AGE = 60 * 60 * 8  # 8 hours
SESSION_MAX_AGE = 60 * 15 #15 mins
#Now the page will auto logoff after 15 mins of inactivity. 


def create_session_cookie(email: str) -> str:
    return _serializer.dumps(email)


def get_current_user(request: Request) -> str | None:
    token = request.cookies.get(SESSION_COOKIE)

    # print("Token:", token)
    # print("SESSION_SECRET:", os.environ.get("SESSION_SECRET"))

    if not token:
        return None
    try:
        user =  _serializer.loads(token, max_age=SESSION_MAX_AGE)
        # print("Decoded User:", user)
        return user
    except Exception as e:
        # print("Cookie Decode Error:", repr(e))
        return None


def is_session_expired(request: Request) -> bool:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return False
    try:
        _serializer.loads(token, max_age=SESSION_MAX_AGE)
        return False
    except SignatureExpired:
        return True
    except BadSignature:
        return False


def get_redirect_target(request: Request) -> str:
    query_string = request.url.query
    if query_string:
        return f"{request.url.path}?{query_string}"
    return request.url.path


def store_redirect_target(request: Request, target: str | None = None) -> str:
    redirect_target = target or get_redirect_target(request)
    request.session[SESSION_REDIRECT_KEY] = redirect_target
    return redirect_target


def _target_job_id(target: str | None) -> str:
    if not target:
        return ""

    parsed = urlparse(target)
    if parsed.path.rstrip("/") != "/application":
        return ""

    return parse_qs(parsed.query).get("job_id", [""])[0].strip()


def _candidate_has_applications(email: str) -> bool:
    from .portal_store import list_applications

    return bool(list_applications(email))
        


router = APIRouter()


# @router.get("/auth/login")
# async def login(request: Request):
#     redirect_uri = str(request.url_for("auth_callback"))
#     return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/auth/login")
async def login(request: Request):
    redirect_uri = "https://eve.pontis.one/auth/callback"
    if request.session.get(SESSION_REDIRECT_KEY) is None:
        next_url = request.query_params.get("next")
        if next_url:
            request.session[SESSION_REDIRECT_KEY] = next_url
    print("Scheme:", request.url.scheme)
    print("Forwarded Proto:", request.headers.get("x-forwarded-proto"))
    print("LOGIN - Scheme:", request.url.scheme)
    print("LOGIN - Forwarded Proto:", request.headers.get("x-forwarded-proto"))
    print("LOGIN - Session:", request.session)
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/auth/callback", name="auth_callback")
async def auth_callback(request: Request):
    print("CALLBACK - Cookies:", request.cookies)
    print("CALLBACK - Session:", request.session)
    print("CALLBACK - State:", request.query_params.get("state"))
    token = await oauth.google.authorize_access_token(request)
    user = token.get("userinfo")
    if not user or not user.get("email"):
        return RedirectResponse("/login")

    next_url = request.session.pop(SESSION_REDIRECT_KEY, "/")
    google_user = {
        "email": user.get("email", ""),
        "name": user.get("name", ""),
        "picture": user.get("picture", ""),
        "sub": user.get("sub", ""),
    }
    request.session["google_user"] = google_user

    response_target = next_url
    try:
        from .portal_store import candidate_exists

        job_id = _target_job_id(next_url)
        has_applications = candidate_exists(google_user["email"]) and _candidate_has_applications(google_user["email"])

        if job_id:
            response_target = next_url
        elif has_applications:
            response_target = "/candidate-dashboard"
        elif response_target in ("", "/"):
            response_target = "/application"
    except Exception:
        if response_target in ("", "/"):
            response_target = "/application"

    response = RedirectResponse(response_target)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=create_session_cookie(user["email"]),
        httponly=True,
        secure=False,      # TEMPORARY
        samesite="lax",
        max_age=SESSION_MAX_AGE,
    )
    return response


@router.get("/auth/logout")
def logout():
    response = RedirectResponse("/login")
    response.delete_cookie(SESSION_COOKIE)
    return response
