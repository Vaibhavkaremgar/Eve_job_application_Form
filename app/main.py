import os
from fastapi import FastAPI, Request, UploadFile, File, Form, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from uuid import UUID
from starlette.middleware.sessions import SessionMiddleware

from .models import CandidateApplication
from .database import get_db
from .crud import create_candidate_application
from .auth import router as auth_router, get_current_user, is_session_expired, SESSION_COOKIE

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key=os.environ["SESSION_SECRET"])
app.include_router(auth_router)

templates = Jinja2Templates(directory="templates")


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    expired = is_session_expired(request)
    resp = templates.TemplateResponse("login.html", {"request": request, "expired": expired})
    if expired:
        resp.delete_cookie(SESSION_COOKIE)
    return resp


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    if not get_current_user(request):
        if is_session_expired(request):
            redirect = RedirectResponse("/login")
            redirect.delete_cookie(SESSION_COOKIE)
            return redirect
        return RedirectResponse("/login")
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/apply")
async def apply(
    request: Request,
    name: str = Form(...),
    email: str = Form(None),
    mobile_number: str = Form(...),
    linkedin_url: str = Form(None),
    job_role: str = Form(...),
    resume: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not get_current_user(request):
        return JSONResponse(status_code=401, content={"success": False, "message": "Unauthorized"})

    resume_data = await resume.read()

    create_candidate_application(
        db=db,
        name=name,
        email=email,
        phone=mobile_number,
        linkedin_url=linkedin_url,
        job_role=job_role,
        resume_data=resume_data,
        resume_filename=resume.filename,
        resume_content_type=resume.content_type,
    )

    return JSONResponse(
        status_code=200,
        content={"success": True, "message": "Application submitted successfully."}
    )


@app.get("/candidate/{candidate_id}/resume")
def get_resume(candidate_id: UUID, db: Session = Depends(get_db)):
    candidate = (
        db.query(CandidateApplication)
        .filter(CandidateApplication.id == candidate_id)
        .first()
    )

    if not candidate:
        return JSONResponse(status_code=404, content={"message": "Candidate not found"})

    return Response(
        content=candidate.resume_data,
        media_type=candidate.resume_content_type,
        headers={"Content-Disposition": f'attachment; filename="{candidate.resume_filename}"'},
    )
