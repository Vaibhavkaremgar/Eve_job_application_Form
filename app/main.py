from fastapi import FastAPI, Request, UploadFile, File, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from fastapi.responses import Response
from uuid import UUID
from .models import CandidateApplication

from .database import get_db
from .crud import create_candidate_application
# from .file_utils import save_resume

app = FastAPI()

templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )


@app.post("/apply")
async def apply(
    name: str = Form(...),
    email: str = Form(None),
    mobile_number: str = Form(...),
    linkedin_url: str = Form(None),
    job_role: str = Form(...),
    resume: UploadFile = File(...),
    db: Session = Depends(get_db),
):

   
    # resume_path = save_resume(resume)
    resume_data = await resume.read()

    
    # candidate = create_candidate_application(
    #     db=db,
    #     name=name,
    #     email=email,
    #     phone=mobile_number,
    #     linkedin_url=linkedin_url,
    #     resume_path=resume_path,
    # )

    candidate = create_candidate_application(
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
    content={
        "success": True,
        "message": "Application submitted successfully."
    }
)
@app.get("/candidate/{candidate_id}/resume")
def get_resume(
    candidate_id: UUID,
    db: Session = Depends(get_db)
):
    candidate = (
        db.query(CandidateApplication)
        .filter(CandidateApplication.id == candidate_id)
        .first()
    )

    if not candidate:
        return JSONResponse(
            status_code=404,
            content={"message": "Candidate not found"}
        )

    return Response(
        content=candidate.resume_data,
        media_type=candidate.resume_content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{candidate.resume_filename}"'
        }
    )