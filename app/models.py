from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from .database import Base


class CandidateApplication(Base):
    __tablename__ = "candidate_applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    name = Column(String, nullable=False)

    email = Column(String, nullable=True)

    phone = Column(String, nullable=False)

    linkedin_url = Column(Text, nullable=True)

    resume_path = Column(Text, nullable=False)

    source = Column(String, default="Career Portal")

    status = Column(String, default="Pending")

    created_at = Column(DateTime, server_default=func.now())