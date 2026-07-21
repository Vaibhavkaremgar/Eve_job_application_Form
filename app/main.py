import os
import logging
import httpx
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from .auth import router as auth_router, get_current_user, is_session_expired, SESSION_COOKIE


def _normalize(value: str | None) -> str:
    """Strip whitespace and lowercase for case-insensitive comparison."""
    return (value or "").strip().lower()


def _is_duplicate(existing_applications: list[dict], name: str, email: str, phone: str, linkedin_url: str | None) -> bool:
    """
    Treat a new submission as a duplicate of an existing application when the
    candidate appears to be the same person, even if one identifier changed.

    Rules (all comparisons are case-insensitive and whitespace-trimmed):
      - Same name + same email + same phone  → duplicate
      - Same name + same phone (email differs) → duplicate
      - Same name + same email (phone differs) → duplicate
      - Same name + same LinkedIn URL (when present on both) → duplicate
    """
    n_name  = _normalize(name)
    n_email = _normalize(email)
    n_phone = _normalize(phone)
    n_linkedin = _normalize(linkedin_url)

    for app in existing_applications:
        e_name     = _normalize(app.get("name"))
        e_email    = _normalize(app.get("email"))
        e_phone    = _normalize(app.get("phone"))
        e_linkedin = _normalize(app.get("linkedin_url"))

        if e_name != n_name:
            continue  # Different person — skip

        # Same name + same email OR same phone → same person
        if e_email == n_email or e_phone == n_phone:
            return True

        # Same name + same LinkedIn URL (non-empty) → same person
        if n_linkedin and e_linkedin and n_linkedin == e_linkedin:
            return True

    return False

logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key=os.environ["SESSION_SECRET"])
app.include_router(auth_router)

templates = Jinja2Templates(directory="templates")

DASHBOARD_BASE_URL = os.environ["DASHBOARD_BASE_URL"]


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    expired = is_session_expired(request)
    resp = templates.TemplateResponse("login.html", {"request": request, "expired": expired})
    if expired:
        resp.delete_cookie(SESSION_COOKIE)
    return resp


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if not get_current_user(request):
        job_id = request.query_params.get("job_id", "")
        next_url = f"/?job_id={job_id}" if job_id else "/"
        login_url = f"/login?next={next_url}" if job_id else "/login"
        if is_session_expired(request):
            redirect = RedirectResponse(login_url)
            redirect.delete_cookie(SESSION_COOKIE)
            return redirect
        return RedirectResponse(login_url)
    job_id = request.query_params.get("job_id", "")
    job_title = ""
    company_name = ""
    job_error = None
    if job_id:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{DASHBOARD_BASE_URL}/api/public/jobs/{job_id}")
            if resp.status_code == 200:
                data = resp.json()
                job_title = data.get("job_title", "")
                company_name = data.get("company_name", "")
            elif resp.status_code in (404, 410):
                job_error = "This job posting is no longer available."
            else:
                logger.warning("Unexpected status fetching job_id=%s: %s", job_id, resp.status_code)
        except httpx.RequestError:
            logger.warning("Could not fetch job details for job_id=%s", job_id)
    else:
        job_error = "No job selected. Please use a valid job application link."
    return templates.TemplateResponse("index.html", {
        "request": request,
        "job_id": job_id,
        "job_title": job_title,
        "company_name": company_name,
        "job_error": job_error,
    })


ALLOWED_EXTENSIONS = {"pdf", "doc", "docx"}


def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[-1].lower() in ALLOWED_EXTENSIONS


@app.post("/apply")
async def apply(
    request: Request,
    job_id: str = Form(...),
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    linkedin_url: str = Form(None),
    resume: UploadFile = File(...),
    cover_letter: UploadFile = File(None),
):
    if not get_current_user(request):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    if not job_id or not job_id.strip():
        return JSONResponse(status_code=400, content={"detail": "job_id is required"})

    if linkedin_url and not linkedin_url.startswith("https://"):
        return JSONResponse(status_code=400, content={"detail": "Please enter a valid LinkedIn profile URL starting with https://"})

    if not _allowed(resume.filename):
        return JSONResponse(status_code=400, content={"detail": "Resume must be a PDF or DOCX file."})
    if cover_letter and cover_letter.filename and not _allowed(cover_letter.filename):
        return JSONResponse(status_code=400, content={"detail": "Cover letter must be a PDF or DOCX file."})

    # --- Duplicate detection: fetch existing applications for this job ---
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            dup_resp = await client.get(
                f"{DASHBOARD_BASE_URL}/api/public/applications",
                params={"job_id": job_id},
            )
        if dup_resp.status_code == 200:
            existing = dup_resp.json() if isinstance(dup_resp.json(), list) else dup_resp.json().get("applications", [])
            if _is_duplicate(existing, name, email, phone, linkedin_url):
                return JSONResponse(status_code=409, content={"detail": "Application already exists."})
        else:
            logger.warning("Could not fetch existing applications for duplicate check — job_id=%s status=%s", job_id, dup_resp.status_code)
    except httpx.RequestError:
        logger.warning("Duplicate check request failed — job_id=%s, proceeding without check", job_id)
    # --- End duplicate detection ---

    logger.info(
        "Forwarding application to Dashboard — job_id=%s email=%s name=%s",
        job_id, email, name,
    )

    files = {"resume": (resume.filename, await resume.read(), resume.content_type)}
    if cover_letter and cover_letter.filename:
        files["cover_letter"] = (cover_letter.filename, await cover_letter.read(), cover_letter.content_type)

    data = {"job_id": job_id, "name": name, "email": email, "phone": phone}
    if linkedin_url:
        data["linkedin_url"] = linkedin_url

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{DASHBOARD_BASE_URL}/api/public/applications",
                data=data,
                files=files,
            )
        logger.info(
            "Dashboard response — status=%s job_id=%s email=%s",
            resp.status_code, job_id, email,
        )
        return JSONResponse(status_code=resp.status_code, content=resp.json())
    except httpx.TimeoutException:
        logger.exception("Dashboard request timed out — job_id=%s email=%s", job_id, email)
        return JSONResponse(status_code=504, content={"detail": "Upstream service timed out."})
    except httpx.RequestError:
        logger.exception("Dashboard request failed — job_id=%s email=%s", job_id, email)
        return JSONResponse(status_code=502, content={"detail": "Could not reach upstream service."})
