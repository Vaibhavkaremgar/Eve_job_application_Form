import os
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

_serializer = URLSafeTimedSerializer(os.environ["SESSION_SECRET"])

SESSION_COOKIE = "candidate_session"
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
        


router = APIRouter()


# @router.get("/auth/login")
# async def login(request: Request):
#     redirect_uri = str(request.url_for("auth_callback"))
#     return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/auth/login")
async def login(request: Request):
    redirect_uri = "https://eve.pontis.one/auth/callback"
    next_url = request.query_params.get("next", "/")
    request.session["next"] = next_url
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

    next_url = request.session.pop("next", "/")
    response = RedirectResponse(next_url)
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
