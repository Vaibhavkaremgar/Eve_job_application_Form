from sqlalchemy.orm import Session
from .models import CandidateApplication


def create_candidate_application(
    db: Session,
    name: str,
    email: str,
    phone: str,
    linkedin_url: str,
    resume_path: str,
):
    candidate = CandidateApplication(
        name=name,
        email=email,
        phone=phone,
        linkedin_url=linkedin_url,
        resume_path=resume_path,
    )

    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    return candidate