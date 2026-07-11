from fastapi import FastAPI, Request, UploadFile, File, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .database import get_db
from .crud import create_candidate_application
from .file_utils import save_resume

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
    resume: UploadFile = File(...),
    db: Session = Depends(get_db),
):

   
    resume_path = save_resume(resume)

    
    candidate = create_candidate_application(
        db=db,
        name=name,
        email=email,
        phone=mobile_number,
        linkedin_url=linkedin_url,
        resume_path=resume_path,
    )

    return JSONResponse(
    status_code=200,
    content={
        "success": True,
        "message": "Application submitted successfully."
    }
)