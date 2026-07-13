from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy import LargeBinary
import uuid

from .database import Base


class CandidateApplication(Base):
    __tablename__ = "candidate_applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    name = Column(String, nullable=False)

    email = Column(String, nullable=True)

    phone = Column(String, nullable=False)

    linkedin_url = Column(Text, nullable=True)

    job_role = Column(String, nullable=True)

    # resume_path = Column(Text, nullable=False)

    resume_data = Column(LargeBinary)

    resume_filename = Column(String(255))

    resume_content_type = Column(String(100))

    source = Column(String, default="Career Portal")

    status = Column(String, default="Pending")

    created_at = Column(DateTime, server_default=func.now())