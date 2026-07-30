from __future__ import annotations

import logging
import os
from pathlib import Path

import httpx
from uuid import UUID
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from .auth import (
    SESSION_COOKIE,
    get_current_user,
    get_redirect_target,
    is_session_expired,
    router as auth_router,
    store_redirect_target,
)
from .portal_store import (
    candidate_exists,
    dashboard_payload,
    format_timestamp,
    get_application_badge_class,
    get_documents,
    get_interviews,
    get_jobs_submitted,
    get_notifications,
    get_profile,
    get_resume,
    upsert_candidate_profile,
)


logger = logging.getLogger(__name__)

app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = BASE_DIR / "uploads"
TEMPLATES_DIR = BASE_DIR / "templates"

app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "dev-secret-change-me"))
app.include_router(auth_router)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
else:
    logger.warning("Static directory not found at %s; skipping /static mount.", STATIC_DIR)

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

DASHBOARD_BASE_URL = os.getenv("DASHBOARD_BASE_URL", "")


def _current_google_user(request: Request) -> dict | None:
    user = request.session.get("google_user")
    return user if isinstance(user, dict) else None


def _current_email(request: Request) -> str | None:
    return get_current_user(request)


def _require_email(request: Request) -> str | None:
    email = _current_email(request)
    if not email:
        return None
    if is_session_expired(request):
        return None
    return email


def _redirect_login(request: Request) -> RedirectResponse:
    store_redirect_target(request, get_redirect_target(request))
    login_url = "/login"
    response = RedirectResponse(login_url, status_code=303)
    if is_session_expired(request):
        response.delete_cookie(SESSION_COOKIE)
    return response


def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[-1].lower() in {"pdf", "doc", "docx"}


def _image_allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[-1].lower() in {"png", "jpg", "jpeg", "webp", "gif"}


def _is_uuid(value: str | None) -> bool:
    if not value:
        return False
    try:
        UUID(str(value))
        return True
    except (TypeError, ValueError):
        return False


def _job_payload_candidates(payload: object) -> list[dict[str, object]]:
    if isinstance(payload, list):
        candidates: list[dict[str, object]] = []
        for item in payload:
            candidates.extend(_job_payload_candidates(item))
        return candidates

    if not isinstance(payload, dict):
        return []

    candidates: list[dict[str, object]] = [payload]
    for value in payload.values():
        candidates.extend(_job_payload_candidates(value))

    seen: set[int] = set()
    unique_candidates: list[dict[str, object]] = []
    for candidate in candidates:
        marker = id(candidate)
        if marker in seen:
            continue
        seen.add(marker)
        unique_candidates.append(candidate)
    return unique_candidates


def _first_text(data: dict[str, object], *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if value is not None and not isinstance(value, (dict, list)):
            text = str(value).strip()
            if text:
                return text
    return ""


def _extract_job_reference(data: dict[str, object], fallback_business_id: str) -> dict[str, str] | None:
    business_job_id = str(
        data.get("business_job_id")
        or data.get("businessJobId")
        or data.get("job_code")
        or data.get("job_number")
        or data.get("job_id")
        or fallback_business_id
    ).strip()
    internal_job_id = (
        data.get("internal_job_id")
        or data.get("internalJobId")
        or data.get("job_uuid")
        or data.get("jobUuid")
        or data.get("uuid")
        or data.get("id")
        or data.get("database_id")
    )
    internal_job_id = str(internal_job_id).strip() if internal_job_id is not None else ""

    if not _is_uuid(internal_job_id):
        return None

    return {
        "business_job_id": business_job_id or fallback_business_id,
        "internal_job_id": internal_job_id,
        "job_title": _first_text(
            data,
            "job_title",
            "jobTitle",
            "job_role",
            "jobRole",
            "role",
            "title",
            "name",
            "job",
        ),
        "company_name": _first_text(data, "company_name", "companyName", "company", "client", "employer"),
    }


def _resolve_job_reference(job_id: str) -> dict[str, str] | None:
    job_id = str(job_id or "").strip()
    if not job_id:
        return None

    logger.info("Received job_id from URL/form: %s", job_id)
    logger.info("Job lookup query: Job.job_id = %s", job_id)

    if not DASHBOARD_BASE_URL:
        logger.warning("DASHBOARD_BASE_URL is not configured; unable to resolve job_id=%s", job_id)
        return None

    lookup_attempts = [
        ("query-param", f"{DASHBOARD_BASE_URL}/api/public/jobs", {"job_id": job_id}),
        ("legacy-path", f"{DASHBOARD_BASE_URL}/api/public/jobs/{job_id}", None),
    ]

    for lookup_type, url, params in lookup_attempts:
        logger.info(
            "Executing job lookup request - source=%s url=%s params=%s",
            lookup_type,
            url,
            params or {},
        )
        try:
            response = httpx.get(url, params=params, timeout=10)
        except httpx.RequestError:
            logger.warning("Could not fetch job details - source=%s job_id=%s", lookup_type, job_id)
            continue

        logger.info("Job lookup response - source=%s status=%s", lookup_type, response.status_code)
        if response.status_code != 200:
            continue

        try:
            payload = response.json()
        except ValueError:
            logger.warning("Job lookup response was not valid JSON - source=%s job_id=%s", lookup_type, job_id)
            continue

        for candidate in _job_payload_candidates(payload):
            reference = _extract_job_reference(candidate, job_id)
            if reference and reference["business_job_id"] == job_id:
                logger.info(
                    "Matching job found - business_job_id=%s internal_job_id=%s job_title=%s company_name=%s",
                    reference["business_job_id"],
                    reference["internal_job_id"],
                    reference["job_title"],
                    reference["company_name"],
                )
                return reference

        logger.info("No matching job found in %s response for job_id=%s", lookup_type, job_id)

    logger.warning("No matching job found for job_id=%s", job_id)
    return None


def _is_duplicate(existing_applications: list[dict], name: str, email: str, phone: str, linkedin_url: str | None) -> bool:
    n_name = (name or "").strip().lower()
    n_email = (email or "").strip().lower()
    n_phone = (phone or "").strip().lower()
    n_linkedin = (linkedin_url or "").strip().lower()

    for application in existing_applications:
        e_name = (application.get("name") or "").strip().lower()
        e_email = (application.get("email") or "").strip().lower()
        e_phone = (application.get("phone") or "").strip().lower()
        e_linkedin = (application.get("linkedin_url") or "").strip().lower()

        if e_name != n_name:
            continue
        if e_email == n_email or e_phone == n_phone:
            return True
        if n_linkedin and e_linkedin and n_linkedin == e_linkedin:
            return True
    return False


def _job_context(job_id: str | None) -> dict[str, str]:
    if not job_id:
        return {"job_id": "", "job_title": "", "company_name": "", "job_error": ""}

    logger.info("Building application form context for job_id=%s", job_id)
    reference = _resolve_job_reference(job_id)
    if reference:
        return {
            "job_id": reference["business_job_id"],
            "job_title": reference["job_title"],
            "company_name": reference["company_name"],
            "job_error": "",
            "internal_job_id": reference["internal_job_id"],
        }

    return {
        "job_id": job_id,
        "job_title": "",
        "company_name": "",
        "job_error": "Job not found",
        "internal_job_id": "",
    }


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    expired = is_session_expired(request)
    next_target = request.query_params.get("next")
    if next_target and request.session.get("post_auth_redirect") is None:
        store_redirect_target(request, next_target)
    resp = templates.TemplateResponse("login.html", {"request": request, "expired": expired})
    if expired:
        resp.delete_cookie(SESSION_COOKIE)
    return resp


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    email = _require_email(request)
    if not email:
        job_id = request.query_params.get("job_id")
        target = "/application"
        if job_id:
            target += f"?job_id={job_id}"
        return RedirectResponse(f"/login?next={target}", status_code=303)

    if candidate_exists(email):
        return RedirectResponse("/candidate-dashboard", status_code=303)

    job_id = request.query_params.get("job_id")
    target = "/application"
    if job_id:
        target += f"?job_id={job_id}"
    return RedirectResponse(target, status_code=303)


@app.get("/application", response_class=HTMLResponse)
def application_page(request: Request):
    email = _require_email(request)
    if not email:
        return _redirect_login(request)

    google_user = _current_google_user(request) or {}
    if candidate_exists(email):
        return RedirectResponse("/candidate-dashboard", status_code=303)

    job_id = request.query_params.get("job_id")
    context = _job_context(job_id)
    profile = get_profile(email, google_user)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "google_user": google_user,
            "profile": profile,
            **context,
        },
    )


@app.get("/candidate-dashboard", response_class=HTMLResponse)
def candidate_dashboard_page(request: Request):
    email = _require_email(request)
    if not email:
        return _redirect_login(request)

    google_user = _current_google_user(request) or {}
    if not candidate_exists(email):
        return RedirectResponse("/application", status_code=303)

    context = dashboard_payload(email, google_user)
    context["request"] = request
    context["candidate"] = context["profile"]
    context["badge_class"] = get_application_badge_class
    context["format_timestamp"] = format_timestamp
    return templates.TemplateResponse("dashboard.html", context)


@app.get("/dashboard", response_class=HTMLResponse)
def legacy_dashboard_redirect():
    return RedirectResponse("/candidate-dashboard", status_code=303)


@app.get("/candidate/dashboard")
def candidate_dashboard_api(request: Request):
    email = _require_email(request)
    if not email:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return dashboard_payload(email, _current_google_user(request))


@app.get("/candidate/profile")
def candidate_profile(request: Request):
    email = _require_email(request)
    if not email:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return get_profile(email, _current_google_user(request))


@app.get("/candidate/resume")
def candidate_resume(request: Request):
    email = _require_email(request)
    if not email:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return {"resume": get_resume(email)}


@app.get("/candidate/jobs-submitted")
def candidate_jobs_submitted(request: Request):
    email = _require_email(request)
    if not email:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return {"jobs_submitted": get_jobs_submitted(email)}


@app.get("/candidate/interviews")
def candidate_interviews(request: Request):
    email = _require_email(request)
    if not email:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return {"interviews": get_interviews(email)}


@app.get("/candidate/notifications")
def candidate_notifications(request: Request):
    email = _require_email(request)
    if not email:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return {"notifications": get_notifications(email)}


@app.get("/candidate/documents")
def candidate_documents(request: Request):
    email = _require_email(request)
    if not email:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return {"documents": get_documents(email)}


@app.put("/candidate/profile")
async def update_profile(
    request: Request,
    name: str | None = Form(None),
    phone: str | None = Form(None),
    linkedin_url: str | None = Form(None),
    current_location: str | None = Form(None),
    preferred_location: str | None = Form(None),
    visa_status: str | None = Form(None),
    experience_years: str | None = Form(None),
    primary_skills: str | None = Form(None),
    secondary_skills: str | None = Form(None),
    profile_picture: UploadFile | None = File(None),
):
    email = _require_email(request)
    if not email:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    if linkedin_url and linkedin_url.strip() and not linkedin_url.strip().startswith("https://"):
        return JSONResponse(status_code=400, content={"detail": "LinkedIn profile URLs must start with https://"})

    picture_bytes = None
    picture_name = None
    if profile_picture and profile_picture.filename:
        if not _image_allowed(profile_picture.filename):
            return JSONResponse(status_code=400, content={"detail": "Profile picture must be a PNG, JPG, JPEG, WEBP, or GIF file."})
        picture_bytes = await profile_picture.read()
        picture_name = profile_picture.filename

    candidate = upsert_candidate_profile(
        email,
        name=name,
        phone=phone,
        linkedin_url=linkedin_url,
        current_location=current_location,
        preferred_location=preferred_location,
        visa_status=visa_status,
        experience_years=experience_years,
        primary_skills=primary_skills,
        secondary_skills=secondary_skills,
        profile_picture_bytes=picture_bytes,
        profile_picture_name=picture_name,
        google_user=_current_google_user(request),
    )
    return {
        "detail": "Profile updated successfully.",
        "profile": get_profile(email, _current_google_user(request)),
        "candidate": candidate,
    }


@app.put("/candidate/resume")
async def update_resume(
    request: Request,
    resume: UploadFile = File(...),
):
    email = _require_email(request)
    if not email:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    if not _allowed(resume.filename):
        return JSONResponse(status_code=400, content={"detail": "Resume must be a PDF, DOC, or DOCX file."})

    resume_bytes = await resume.read()
    candidate = upsert_candidate_profile(
        email,
        resume_bytes=resume_bytes,
        resume_name=resume.filename,
        google_user=_current_google_user(request),
    )
    return {"detail": "Resume updated successfully.", "resume": get_resume(email), "candidate": candidate}


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
    if not _require_email(request):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    if not job_id or not job_id.strip():
        return JSONResponse(status_code=400, content={"detail": "job_id is required"})

    reference = _resolve_job_reference(job_id)
    if not reference:
        return JSONResponse(status_code=404, content={"detail": "Job not found"})

    internal_job_id = reference["internal_job_id"]

    if linkedin_url and not linkedin_url.startswith("https://"):
        return JSONResponse(
            status_code=400,
            content={"detail": "Please enter a valid LinkedIn profile URL starting with https://"},
        )

    if not _allowed(resume.filename):
        return JSONResponse(status_code=400, content={"detail": "Resume must be a PDF, DOC, or DOCX file."})
    if cover_letter and cover_letter.filename and not _allowed(cover_letter.filename):
        return JSONResponse(status_code=400, content={"detail": "Cover letter must be a PDF, DOC, or DOCX file."})

    resume_bytes = await resume.read()
    cover_letter_bytes = await cover_letter.read() if cover_letter and cover_letter.filename else None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            dup_resp = await client.get(
                f"{DASHBOARD_BASE_URL}/api/public/applications",
                params={"job_id": internal_job_id},
            )

        if dup_resp.status_code == 200:
            payload = dup_resp.json()
            existing = payload if isinstance(payload, list) else payload.get("applications", [])
            if _is_duplicate(existing, name, email, phone, linkedin_url):
                return JSONResponse(status_code=409, content={"detail": "Application already exists."})
        else:
            logger.warning(
                "Could not fetch existing applications for duplicate check - job_id=%s status=%s",
                internal_job_id,
                dup_resp.status_code,
            )
    except httpx.RequestError:
        logger.warning("Duplicate check request failed - job_id=%s, proceeding without check", internal_job_id)

    logger.info("Forwarding application to Dashboard - job_id=%s email=%s name=%s", internal_job_id, email, name)

    files = {"resume": (resume.filename, resume_bytes, resume.content_type)}
    if cover_letter and cover_letter.filename and cover_letter_bytes is not None:
        files["cover_letter"] = (cover_letter.filename, cover_letter_bytes, cover_letter.content_type)

    data = {"job_id": internal_job_id, "name": name, "email": email, "phone": phone}
    if linkedin_url:
        data["linkedin_url"] = linkedin_url

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{DASHBOARD_BASE_URL}/api/public/applications",
                data=data,
                files=files,
            )

        response_json = resp.json() if resp.content else {}
        if isinstance(response_json, dict):
            response_json.setdefault("dashboard_url", "/candidate-dashboard")
        if resp.status_code < 400:
            try:
                upsert_candidate_profile(
                    email,
                    name=name,
                    phone=phone,
                    linkedin_url=linkedin_url,
                    resume_bytes=resume_bytes,
                    resume_name=resume.filename,
                    cover_letter_bytes=cover_letter_bytes,
                    cover_letter_name=cover_letter.filename if cover_letter and cover_letter.filename else None,
                    google_user=_current_google_user(request),
                    job_id=internal_job_id,
                    business_job_id=reference["business_job_id"],
                )
            except Exception:
                logger.exception("Failed to mirror candidate locally for %s", email)
        logger.info("Dashboard response - status=%s job_id=%s email=%s", resp.status_code, internal_job_id, email)
        return JSONResponse(status_code=resp.status_code, content=response_json)
    except httpx.TimeoutException:
        logger.exception("Dashboard request timed out - job_id=%s email=%s", internal_job_id, email)
        return JSONResponse(status_code=504, content={"detail": "Upstream service timed out."})
    except httpx.RequestError:
        logger.exception("Dashboard request failed - job_id=%s email=%s", internal_job_id, email)
        return JSONResponse(status_code=502, content={"detail": "Could not reach upstream service."})
