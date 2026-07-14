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

SESSION_COOKIE = "session"
SESSION_MAX_AGE = 60 * 60 * 8  # 8 hours


def create_session_cookie(email: str) -> str:
    return _serializer.dumps(email)


def get_current_user(request: Request) -> str | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    try:
        return _serializer.loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


router = APIRouter()


# @router.get("/auth/login")
# async def login(request: Request):
#     redirect_uri = str(request.url_for("auth_callback"))
#     return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/auth/login")
async def login(request: Request):
    # redirect_uri = str(request.url_for("auth_callback"))
    redirect_uri = "https://eve.pontis.one/auth/callback"
    # print("Redirect URI:", redirect_uri)
    print("Request URL:", request.url)
    print("Base URL:", request.base_url)
    print("Redirect URI:", redirect_uri)
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/auth/callback", name="auth_callback")
async def auth_callback(request: Request):
    token = await oauth.google.authorize_access_token(request)
    user = token.get("userinfo")
    if not user or not user.get("email"):
        return RedirectResponse("/login")

    response = RedirectResponse("/")
    response.set_cookie(
        key=SESSION_COOKIE,
        value=create_session_cookie(user["email"]),
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
    )
    return response


@router.get("/auth/logout")
def logout():
    response = RedirectResponse("/login")
    response.delete_cookie(SESSION_COOKIE)
    return response
