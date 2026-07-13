from sqlalchemy.orm import Session
from .models import CandidateApplication


def create_candidate_application(
    db: Session,
    name: str,
    email: str,
    phone: str,
    linkedin_url: str,
    job_role: str,
    # resume_path: str,
    resume_data: bytes,
    resume_filename: str,   
    resume_content_type: str
):
    candidate = CandidateApplication(
        name=name,
        email=email,
        phone=phone,
        linkedin_url=linkedin_url,
        job_role=job_role,
        # resume_path=resume_path,
        resume_data=resume_data,
        resume_filename=resume_filename,
        resume_content_type=resume_content_type,
    )
        
    

    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    return candidate