from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = BASE_DIR / "uploads"
STORE_PATH = DATA_DIR / "candidate_portal.json"

APPLICATION_STAGES = [
    "Applied",
    "Resume Reviewed",
    "Shortlisted",
    "Interview Scheduled",
    "Interview Completed",
    "Offer",
]

JOB_CATALOG: list[dict[str, Any]] = [
    {
        "job_id": "job-fullstack-001",
        "job": "Senior Full Stack Engineer",
        "company": "Pontis",
        "experience": "5-8 years",
        "location": "Bengaluru, India",
        "salary": "INR 24-34 LPA",
        "skills": ["python", "fastapi", "react", "postgresql"],
        "description": "Build customer-facing product surfaces and internal workflow tools.",
    },
    {
        "job_id": "job-backend-002",
        "job": "Backend Python Engineer",
        "company": "Northstar Labs",
        "experience": "3-6 years",
        "location": "Remote",
        "salary": "$120k - $165k",
        "skills": ["python", "api", "postgresql", "docker"],
        "description": "Own API services, integrations, and performance-sensitive workflows.",
    },
    {
        "job_id": "job-data-003",
        "job": "Data Analyst",
        "company": "Orbit Health",
        "experience": "2-5 years",
        "location": "Hyderabad, India",
        "salary": "INR 14-20 LPA",
        "skills": ["sql", "excel", "python", "analytics"],
        "description": "Transform product and operations data into actionable insights.",
    },
    {
        "job_id": "job-product-004",
        "job": "Product Designer",
        "company": "AsterWorks",
        "experience": "4-7 years",
        "location": "Remote",
        "salary": "$100k - $145k",
        "skills": ["figma", "ui", "ux", "research"],
        "description": "Design polished enterprise experiences with a systems mindset.",
    },
    {
        "job_id": "job-devops-005",
        "job": "DevOps Engineer",
        "company": "CloudForge",
        "experience": "4-8 years",
        "location": "Pune, India",
        "salary": "INR 20-30 LPA",
        "skills": ["docker", "kubernetes", "linux", "aws"],
        "description": "Shape delivery, observability, and secure platform operations.",
    },
    {
        "job_id": "job-qa-006",
        "job": "QA Automation Engineer",
        "company": "NovaStack",
        "experience": "2-5 years",
        "location": "Remote",
        "salary": "$90k - $125k",
        "skills": ["testing", "automation", "python", "api"],
        "description": "Create reliable automation around critical candidate journeys.",
    },
    {
        "job_id": "job-frontend-007",
        "job": "UI Engineer",
        "company": "BluePeak",
        "experience": "3-6 years",
        "location": "Bengaluru, India",
        "salary": "INR 18-28 LPA",
        "skills": ["html", "css", "javascript", "react"],
        "description": "Build accessible and animated product interfaces with care.",
    },
    {
        "job_id": "job-cs-008",
        "job": "Customer Success Associate",
        "company": "Harbor AI",
        "experience": "1-3 years",
        "location": "Remote",
        "salary": "$70k - $95k",
        "skills": ["communication", "presentation", "crm", "support"],
        "description": "Help customers onboard and adopt the product successfully.",
    },
]

SKILL_KEYWORDS: dict[str, tuple[str, ...]] = {
    "python": ("python", "flask", "fastapi", "django", "pandas"),
    "react": ("react", "next.js", "nextjs", "frontend"),
    "html": ("html", "markup", "web"),
    "css": ("css", "tailwind", "sass", "styling"),
    "javascript": ("javascript", "typescript", "js", "node"),
    "postgresql": ("postgres", "postgresql", "sql", "database"),
    "docker": ("docker", "containers", "container"),
    "kubernetes": ("kubernetes", "k8s"),
    "linux": ("linux", "ubuntu", "shell"),
    "aws": ("aws", "cloud", "ec2", "s3"),
    "figma": ("figma", "design"),
    "ui": ("ui", "user interface", "interfaces"),
    "ux": ("ux", "research", "journey"),
    "testing": ("test", "testing", "qa"),
    "automation": ("automation", "automate", "selenium", "playwright"),
    "api": ("api", "rest", "graphql"),
    "analytics": ("analytics", "analysis", "insights"),
    "excel": ("excel", "sheets"),
    "support": ("support", "customer success", "success"),
    "communication": ("communication", "presentation", "stakeholder"),
    "crm": ("crm", "salesforce", "hubspot"),
}

STATUS_META = {
    "Applied": {"tone": "blue", "label": "Submitted"},
    "Resume Reviewed": {"tone": "indigo", "label": "Under Review"},
    "Shortlisted": {"tone": "green", "label": "Shortlisted"},
    "Interview Scheduled": {"tone": "amber", "label": "Interview Scheduled"},
    "Interview Completed": {"tone": "slate", "label": "Interview Completed"},
    "Offer": {"tone": "emerald", "label": "Offer Received"},
    "Rejected": {"tone": "rose", "label": "Rejected"},
}

IN_PROGRESS_STATUSES = {
    "Applied",
    "Resume Reviewed",
    "Shortlisted",
    "Interview Scheduled",
    "Interview Completed",
}

FINAL_APPLICATION_STATUSES = {
    "Rejected",
    "Withdrawn",
    "Closed",
}

_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug_email(email: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", (email or "").strip().lower()).strip("_") or "candidate"


def _safe_filename(filename: str) -> str:
    clean = Path(filename).name
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", clean)
    return clean or "upload.bin"


def _default_store() -> dict[str, Any]:
    return {"candidates": {}}


def _ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _read_store() -> dict[str, Any]:
    _ensure_dirs()
    print("STORE PATH:", STORE_PATH)
    print("STORE EXISTS:", STORE_PATH.exists())

    if not STORE_PATH.exists():
        print("STORE FILE NOT FOUND")
        return _default_store()
    try:
        with STORE_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            print("STORE CANDIDATE COUNT:", len(data.get("candidates", {})))
        if not isinstance(data, dict):
            return _default_store()
        data.setdefault("candidates", {})
        return data
    except json.JSONDecodeError:
        print("STORE JSON DECODE ERROR")
        return _default_store()


def _write_store(store: dict[str, Any]) -> None:
    _ensure_dirs()
    print("========== SAVING STORE ==========")
    print("SAVING STORE TO:", STORE_PATH)
    print("CANDIDATE COUNT:", len(store.get("candidates", {})))
    print("CANDIDATE KEYS:", list(store.get("candidates", {}).keys())[:10])
    print("==================================")
    temp_path = STORE_PATH.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(store, handle, indent=2, ensure_ascii=True)
    temp_path.replace(STORE_PATH)


def with_store() -> dict[str, Any]:
    with _LOCK:
        return _read_store()


def save_store(store: dict[str, Any]) -> None:
    with _LOCK:
        _write_store(store)


# def get_candidate(email: str) -> dict[str, Any] | None:
#     store = with_store()
#     return store.get("candidates", {}).get(email.lower().strip())

def get_candidate(email: str) -> dict[str, Any] | None:
    store = with_store()

    print("Candidate lookup:", email.lower().strip())
    print("Candidate keys:", list(store.get("candidates", {}).keys())[:20])

    return store.get("candidates", {}).get(email.lower().strip())


def candidate_exists(email: str) -> bool:
    return get_candidate(email) is not None


def _extract_resume_text(file_name: str, file_bytes: bytes) -> str:
    text = file_bytes.decode("utf-8", errors="ignore")
    text = re.sub(r"\s+", " ", text)
    return f"{file_name} {text}".strip().lower()


def infer_skills(*text_chunks: str) -> list[str]:
    haystack = " ".join(chunk or "" for chunk in text_chunks).lower()
    skills: list[str] = []
    for skill, keywords in SKILL_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            skills.append(skill)
    return skills


def _resume_storage_paths(email: str, filename: str) -> tuple[Path, str]:
    candidate_dir = UPLOAD_DIR / _slug_email(email)
    candidate_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(filename)
    stamped = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}_{safe_name}"
    return candidate_dir / stamped, stamped


def _store_uploaded_file(email: str, filename: str, file_bytes: bytes) -> dict[str, str]:
    path, stored_name = _resume_storage_paths(email, filename)
    path.write_bytes(file_bytes)
    return {
        "filename": Path(filename).name,
        "stored_name": stored_name,
        "path": str(path),
        "download_url": f"/uploads/{_slug_email(email)}/{stored_name}",
    }


def _status_meta(status: str) -> dict[str, str]:
    return STATUS_META.get(status, {"tone": "slate", "label": status})


def _badge_class(status: str) -> str:
    tone = _status_meta(status)["tone"]
    return f"badge badge-{tone}"


def _stage_progress(status: str) -> list[dict[str, Any]]:
    try:
        current_index = APPLICATION_STAGES.index(status)
    except ValueError:
        current_index = 0

    timeline: list[dict[str, Any]] = []
    for index, stage in enumerate(APPLICATION_STAGES):
        timeline.append(
            {
                "label": stage,
                "done": index <= current_index,
                "active": index == current_index,
            }
        )
    return timeline


def _sort_applications(applications: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(applications, key=lambda item: item.get("applied_at", ""), reverse=True)


def _business_job_id(application: dict[str, Any]) -> str:
    return (
        application.get("business_job_id")
        or application.get("display_job_id")
        or application.get("job_code")
        or application.get("job_id", "")
    )


def _seed_candidate(email: str, google_user: dict[str, Any] | None = None) -> dict[str, Any]:
    google_user = google_user or {}
    return {
        "email": email,
        "name": google_user.get("name", ""),
        "phone": "",
        "linkedin_url": "",
        "current_location": "",
        "preferred_location": "",
        "visa_status": "",
        "experience_years": "",
        "primary_skills": [],
        "secondary_skills": [],
        "profile_picture": google_user.get("picture", ""),
        "google_picture": google_user.get("picture", ""),
        "resume": None,
        "resume_text": "",
        "skills": [],
        "applications": [],
        "interviews": [],
        "documents": [],
        "notifications": [],
        "created_at": _now(),
        "updated_at": _now(),
        "last_login_at": _now(),
        "notification_preferences": {
            "interview": True,
            "status": True,
            "jobs": True,
            "offer": True,
        },
    }


def ensure_candidate(email: str, google_user: dict[str, Any] | None = None) -> dict[str, Any]:
    email_key = email.lower().strip()
    store = with_store()
    candidate = store["candidates"].get(email_key)
    if not candidate:
        candidate = _seed_candidate(email_key, google_user)
        store["candidates"][email_key] = candidate
        save_store(store)
    elif google_user:
        candidate.setdefault("google_picture", google_user.get("picture", ""))
        candidate.setdefault("name", google_user.get("name", candidate.get("name", "")))
        candidate["last_login_at"] = _now()
        store["candidates"][email_key] = candidate
        save_store(store)
    return candidate


def upsert_candidate_profile(
    email: str,
    *,
    name: str | None = None,
    phone: str | None = None,
    linkedin_url: str | None = None,
    current_location: str | None = None,
    preferred_location: str | None = None,
    visa_status: str | None = None,
    experience_years: str | None = None,
    primary_skills: str | list[str] | None = None,
    secondary_skills: str | list[str] | None = None,
    google_user: dict[str, Any] | None = None,
    profile_picture_bytes: bytes | None = None,
    profile_picture_name: str | None = None,
    resume_bytes: bytes | None = None,
    resume_name: str | None = None,
    cover_letter_bytes: bytes | None = None,
    cover_letter_name: str | None = None,
    job_id: str | None = None,
    business_job_id: str | None = None,
) -> dict[str, Any]:
    email_key = email.lower().strip()
    store = with_store()
    candidate = store["candidates"].get(email_key) or _seed_candidate(email_key, google_user)
    if name is not None:
        candidate["name"] = name.strip()
    if phone is not None:
        candidate["phone"] = phone.strip()
    if linkedin_url is not None:
        candidate["linkedin_url"] = linkedin_url.strip()
    if current_location is not None:
        candidate["current_location"] = current_location.strip()
    if preferred_location is not None:
        candidate["preferred_location"] = preferred_location.strip()
    if visa_status is not None:
        candidate["visa_status"] = visa_status.strip()
    if experience_years is not None:
        candidate["experience_years"] = experience_years.strip()
    if primary_skills is not None:
        if isinstance(primary_skills, str):
            candidate["primary_skills"] = [item.strip() for item in primary_skills.split(",") if item.strip()]
        else:
            candidate["primary_skills"] = [item.strip() for item in primary_skills if item.strip()]
    if secondary_skills is not None:
        if isinstance(secondary_skills, str):
            candidate["secondary_skills"] = [item.strip() for item in secondary_skills.split(",") if item.strip()]
        else:
            candidate["secondary_skills"] = [item.strip() for item in secondary_skills if item.strip()]
    if google_user:
        candidate["google_picture"] = google_user.get("picture", candidate.get("google_picture", ""))
        candidate.setdefault("name", google_user.get("name", ""))

    if profile_picture_bytes and profile_picture_name:
        stored = _store_uploaded_file(email_key, profile_picture_name, profile_picture_bytes)
        candidate["profile_picture"] = stored["download_url"]
        candidate["profile_picture_file"] = stored

    if resume_bytes and resume_name:
        stored = _store_uploaded_file(email_key, resume_name, resume_bytes)
        candidate["resume"] = stored
        resume_text = _extract_resume_text(resume_name, resume_bytes)
        candidate["resume_text"] = resume_text
        inferred = infer_skills(candidate.get("name", ""), candidate.get("linkedin_url", ""), resume_text)
        candidate["skills"] = inferred
        candidate["primary_skills"] = candidate.get("primary_skills") or inferred[:5]
        candidate["secondary_skills"] = candidate.get("secondary_skills") or inferred[5:10]

    if cover_letter_bytes and cover_letter_name:
        candidate["cover_letter"] = _store_uploaded_file(email_key, cover_letter_name, cover_letter_bytes)

    candidate["updated_at"] = _now()
    candidate["last_login_at"] = _now()
    store["candidates"][email_key] = candidate

    if job_id is not None:
        job = get_job(job_id)
        if job:
            job = {**job, "business_job_id": business_job_id or job.get("business_job_id") or job_id}
            _add_application(store, candidate, job, source="application-form")
        else:
            _add_application(
                store,
                candidate,
                {
                    "job_id": job_id,
                    "business_job_id": business_job_id or job_id,
                    "job": "Candidate Application",
                    "company": "Pontis",
                    "experience": "N/A",
                    "location": "Remote",
                    "salary": "Confidential",
                    "skills": [],
                    "description": "Submitted from the candidate portal.",
                },
                source="application-form",
            )
    elif not candidate.get("applications"):
        _add_application(
            store,
            candidate,
            {
                "job_id": "candidate-onboarding",
                "business_job_id": "candidate-onboarding",
                "job": "Candidate Profile Submission",
                "company": "Pontis",
                "experience": "N/A",
                "location": "Remote",
                "salary": "Confidential",
                "skills": [],
                "description": "Initial candidate portal profile submission.",
            },
            source="application-form",
        )

    save_store(store)
    return candidate


def _add_application(
    store: dict[str, Any],
    candidate: dict[str, Any],
    job: dict[str, Any],
    *,
    source: str,
) -> dict[str, Any]:
    applications = candidate.setdefault("applications", [])
    job_id = job.get("job_id")
    business_job_id = job.get("business_job_id") or job_id
    if any(item.get("job_id") == job_id for item in applications):
        return next(item for item in applications if item.get("job_id") == job_id)

    application = {
        "id": uuid.uuid4().hex,
        "job_id": job_id,
        "business_job_id": business_job_id,
        "job": job.get("job"),
        "company": job.get("company"),
        "experience": job.get("experience", ""),
        "location": job.get("location", ""),
        "salary": job.get("salary", ""),
        "applied_at": _now(),
        "current_status": "Applied",
        "status_badge": _badge_class("Applied"),
        "timeline": _stage_progress("Applied"),
        "source": source,
        "description": job.get("description", ""),
    }
    applications.append(application)
    candidate["applications"] = _sort_applications(applications)
    candidate.setdefault("notifications", []).insert(
        0,
        {
            "id": uuid.uuid4().hex,
            "type": "status",
            "title": f"Application received for {job.get('job')}",
            "message": "We have saved your application and will keep the candidate updated from this dashboard.",
            "created_at": _now(),
            "read": False,
        },
    )
    store["candidates"][candidate["email"]] = candidate
    return application


def apply_to_job(email: str, job_id: str) -> dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise KeyError(job_id)
    store = with_store()
    candidate = store["candidates"].get(email.lower().strip())
    if not candidate:
        candidate = _seed_candidate(email)
        store["candidates"][email.lower().strip()] = candidate
    application = _add_application(store, candidate, job, source="dashboard")
    candidate["updated_at"] = _now()
    candidate["last_login_at"] = _now()
    save_store(store)
    return application


def get_job(job_id: str) -> dict[str, Any] | None:
    for job in JOB_CATALOG:
        if job["job_id"] == job_id or job.get("business_job_id") == job_id or job.get("id") == job_id:
            return dict(job)
    return None


def list_applications(email: str) -> list[dict[str, Any]]:
    candidate = get_candidate(email)
    if not candidate:
        return []
    applications = _sort_applications(candidate.get("applications", []))
    return [
        {
            **application,
            "status_label": _status_meta(application.get("current_status", "Applied"))["label"],
            "status_badge": _badge_class(application.get("current_status", "Applied")),
        }
        for application in applications
    ]

def has_applied_to_job(email: str, business_job_id: str) -> bool:
    applications = list_applications(email)

    return any(
        application.get("business_job_id") == business_job_id
        for application in applications
    )

def get_resume(email: str) -> dict[str, Any] | None:
    candidate = get_candidate(email)
    if not candidate:
        return None
    resume = candidate.get("resume")
    if not resume:
        return None
    return {
        "name": resume.get("filename", "Resume"),
        "uploaded_at": candidate.get("updated_at", candidate.get("created_at")),
        "download_url": resume.get("download_url"),
        "path": resume.get("path"),
        "skills": candidate.get("skills", []),
    }


def get_profile(email: str, google_user: dict[str, Any] | None = None) -> dict[str, Any]:
    candidate = get_candidate(email) or {}
    profile_picture = candidate.get("profile_picture") or candidate.get("google_picture") or (google_user or {}).get("picture", "")
    return {
        "email": candidate.get("email", email),
        "name": candidate.get("name", (google_user or {}).get("name", "")),
        "phone": candidate.get("phone", ""),
        "linkedin_url": candidate.get("linkedin_url", ""),
        "current_location": candidate.get("current_location", ""),
        "preferred_location": candidate.get("preferred_location", ""),
        "visa_status": candidate.get("visa_status", ""),
        "experience_years": candidate.get("experience_years", ""),
        "primary_skills": candidate.get("primary_skills", []),
        "secondary_skills": candidate.get("secondary_skills", []),
        "profile_picture": profile_picture,
        "google_picture": candidate.get("google_picture", (google_user or {}).get("picture", "")),
        "resume": get_resume(email),
        "skills": candidate.get("skills", []),
        "updated_at": candidate.get("updated_at"),
    }


def get_jobs_submitted(email: str) -> list[dict[str, Any]]:
    return [
        {
            **application,
            "business_job_id": _business_job_id(application),
        }
        for application in list_applications(email)
    ]


def get_interviews(email: str) -> list[dict[str, Any]]:
    candidate = get_candidate(email)
    if not candidate:
        return []

    stored = candidate.get("interviews")
    if isinstance(stored, list) and stored:
        return stored

    interviews: list[dict[str, Any]] = []
    for application in list_applications(email):
        status = application.get("current_status", "Applied")
        if status not in {"Interview Scheduled", "Interview Completed", "Shortlisted", "Offer"}:
            continue
        applied_at = application.get("applied_at")
        interview_date = ""
        if applied_at:
            try:
                interview_date = (datetime.fromisoformat(applied_at.replace("Z", "+00:00")) + timedelta(days=7)).isoformat()
            except ValueError:
                interview_date = applied_at
        interviews.append(
            {
                "id": f"interview-{application.get('id')}",
                "business_job_id": _business_job_id(application),
                "job_title": application.get("job", ""),
                "client": application.get("company", ""),
                "interview_date": interview_date,
                "interview_time": "To be confirmed",
                "interview_type": "Client interview",
                "meeting_link": "",
                "current_status": status,
            }
        )
    return interviews


def get_documents(email: str) -> list[dict[str, Any]]:
    candidate = get_candidate(email)
    if not candidate:
        return []

    documents: list[dict[str, Any]] = []
    resume = get_resume(email)
    if resume:
        documents.append(
            {
                "id": "resume",
                "name": "Resume",
                "description": "Current resume uploaded for your candidate profile.",
                "uploaded_at": resume.get("uploaded_at"),
                "download_url": resume.get("download_url"),
                "available": True,
            }
        )
        documents.append(
            {
                "id": "updated-resume",
                "name": "Updated Resume",
                "description": "Latest resume file available to the recruitment team.",
                "uploaded_at": resume.get("uploaded_at"),
                "download_url": resume.get("download_url"),
                "available": True,
            }
        )
    else:
        documents.append(
            {
                "id": "resume",
                "name": "Resume",
                "description": "Upload a resume to make this downloadable.",
                "uploaded_at": None,
                "download_url": "",
                "available": False,
            }
        )

    for future_name in ("Offer Letter", "Joining Letter"):
        documents.append(
            {
                "id": future_name.lower().replace(" ", "-"),
                "name": future_name,
                "description": "Coming soon.",
                "uploaded_at": None,
                "download_url": "",
                "available": False,
            }
        )

    return documents


def get_profile_status(email: str) -> list[dict[str, Any]]:
    candidate = get_candidate(email)
    if not candidate:
        return []

    resume = candidate.get("resume")
    applications = list_applications(email)
    latest_status = applications[0].get("current_status", "Applied") if applications else "Applied"
    has_marketing = latest_status in {"Shortlisted", "Interview Scheduled", "Interview Completed", "Offer"}
    return [
        {"label": "Profile Created", "done": True},
        {"label": "Resume Uploaded", "done": bool(resume)},
        {"label": "Resume Reviewed", "done": bool(applications) and latest_status != "Applied"},
        {"label": "Skills Extracted", "done": bool(candidate.get("skills"))},
        {"label": "Ready for Marketing", "done": bool(resume) and bool(candidate.get("skills"))},
        {"label": "Marketing In Progress", "done": has_marketing},
    ]


def get_summary(email: str) -> dict[str, int]:
    applications = list_applications(email)
    summary = {
        "applications_submitted": len(applications),
        "applications_under_review": 0,
        "interview_scheduled": 0,
        "rejected": 0,
        "offers": 0,
    }
    for application in applications:
        status = application.get("current_status", "Applied")
        if status in {"Applied", "Resume Reviewed"}:
            summary["applications_under_review"] += 1
        elif status == "Interview Scheduled":
            summary["interview_scheduled"] += 1
        elif status == "Rejected":
            summary["rejected"] += 1
        elif status == "Offer":
            summary["offers"] += 1
    return summary


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _candidate_documents(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for key in ("resume", "cover_letter"):
        document = candidate.get(key)
        if isinstance(document, dict):
            documents.append(document)

    extra_documents = candidate.get("documents")
    if isinstance(extra_documents, list):
        for document in extra_documents:
            if isinstance(document, dict):
                documents.append(document)

    return documents


def _count_uploaded_documents(candidate: dict[str, Any]) -> int:
    seen: set[str] = set()
    total = 0
    for document in _candidate_documents(candidate):
        unique_key = (
            str(document.get("download_url") or document.get("path") or document.get("stored_name") or document.get("id") or document.get("name") or "").strip()
        )
        if not unique_key or unique_key in seen:
            continue
        if not (document.get("download_url") or document.get("path") or document.get("stored_name")):
            continue
        seen.add(unique_key)
        total += 1
    return total


def _count_matching_jobs(email: str) -> int:
    candidate = get_candidate(email) or {}
    profile = get_profile(email)

    skills = {
        str(skill).strip().lower()
        for skill in candidate.get("skills", [])
        if isinstance(skill, str) and skill.strip()
    }
    skills.update(
        str(skill).strip().lower()
        for skill in candidate.get("primary_skills", [])
        if isinstance(skill, str) and skill.strip()
    )
    skills.update(
        str(skill).strip().lower()
        for skill in candidate.get("secondary_skills", [])
        if isinstance(skill, str) and skill.strip()
    )

    preferred_location = str(profile.get("preferred_location", "") or "").strip().lower()
    matched = 0

    for job in JOB_CATALOG:
        job_skills = {
            str(skill).strip().lower()
            for skill in job.get("skills", [])
            if isinstance(skill, str) and skill.strip()
        }
        score = len(skills.intersection(job_skills))
        if preferred_location and preferred_location in str(job.get("location", "")).lower():
            score += 1
        if score > 0:
            matched += 1

    return matched


def _count_upcoming_interviews(email: str) -> int:
    now = datetime.now(timezone.utc)
    total = 0

    for interview in get_interviews(email):
        status = str(interview.get("current_status", "") or "")
        if status != "Interview Scheduled":
            continue
        interview_date = _parse_datetime(interview.get("interview_date"))
        if interview_date is None or interview_date > now:
            total += 1

    return total


def _count_applications_by_status(email: str, *, allowed: set[str], excluded: set[str] | None = None) -> int:
    excluded = excluded or set()
    total = 0
    for application in list_applications(email):
        status = str(application.get("current_status", "Applied") or "Applied")
        if status in excluded:
            continue
        if status in allowed:
            total += 1
    return total


def _count_active_applications(email: str) -> int:
    total = 0
    for application in list_applications(email):
        status = str(application.get("current_status", "Applied") or "Applied")
        if status not in FINAL_APPLICATION_STATUSES:
            total += 1
    return total


def get_kpi_summary(email: str) -> dict[str, int]:
    applications = list_applications(email)
    candidate = get_candidate(email) or {}

    # TODO: Source these KPI values from dedicated backend analytics APIs if/when they become available.
    # matching_jobs -> candidate matching analytics endpoint
    # applications_submitted -> applications list endpoint
    # applications_in_progress -> application status aggregation endpoint
    # upcoming_interviews -> interviews endpoint
    # documents_uploaded -> documents/profile files endpoint
    # active_applications -> active application status aggregation endpoint
    return {
        "matching_jobs": _count_matching_jobs(email),
        "applications_submitted": len(applications),
        "applications_in_progress": _count_applications_by_status(
            email,
            allowed=IN_PROGRESS_STATUSES,
        ),
        "upcoming_interviews": _count_upcoming_interviews(email),
        "documents_uploaded": _count_uploaded_documents(candidate),
        "active_applications": _count_active_applications(email),
    }


def get_recommended_jobs(email: str) -> list[dict[str, Any]]:
    candidate = get_candidate(email)
    if not candidate:
        return []
    skills = set(candidate.get("skills", []))
    recommendations: list[dict[str, Any]] = []
    for job in JOB_CATALOG:
        overlap = skills.intersection(job.get("skills", []))
        score = len(overlap)
        if score == 0 and not skills:
            score = 1
        if score > 0:
            recommendations.append(
                {
                    **job,
                    "match_score": score,
                    "matched_skills": sorted(overlap),
                }
            )
    if not recommendations:
        recommendations = [
            {
                **job,
                "match_score": 1 if index < 3 else 0,
                "matched_skills": [],
            }
            for index, job in enumerate(JOB_CATALOG[:4])
        ]
    recommendations.sort(key=lambda item: (item.get("match_score", 0), item.get("job", "")), reverse=True)
    return recommendations[:4]


def get_notifications(email: str) -> list[dict[str, Any]]:
    candidate = get_candidate(email)
    if not candidate:
        return []
    notifications = list(candidate.get("notifications", []))
    if candidate.get("resume"):
        notifications.insert(
            0,
            {
                "id": f"resume-{candidate['email']}",
                "type": "resume",
                "title": "Resume ready",
                "message": f"{candidate['resume'].get('filename', 'Your resume')} is available for download.",
                "created_at": candidate.get("updated_at"),
                "read": False,
            },
        )
    recommendations = get_recommended_jobs(email)
    if recommendations:
        notifications.insert(
            0,
            {
                "id": f"jobs-{candidate['email']}",
                "type": "jobs",
                "title": "New matching jobs",
                "message": f"We found {len(recommendations)} jobs that match your resume profile.",
                "created_at": _now(),
                "read": False,
            },
        )
    if candidate.get("applications"):
        latest = list_applications(email)[0]
        notifications.insert(
            0,
            {
                "id": f"status-{latest['id']}",
                "type": "status",
                "title": f"{latest['job']} is {latest['current_status']}",
                "message": "Track the status from the Jobs Submitted section.",
                "created_at": latest.get("applied_at"),
                "read": False,
            },
        )
    return notifications[:8]


def get_timeline(email: str) -> list[dict[str, Any]]:
    applications = list_applications(email)
    if not applications:
        return _stage_progress("Applied")
    return applications[0].get("timeline", _stage_progress("Applied"))


def dashboard_payload(email: str, google_user: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = get_profile(email, google_user)
    return {
        "profile": profile,
        "summary": get_summary(email),
        "kpis": get_kpi_summary(email),
        "jobs_submitted": get_jobs_submitted(email),
        "applications": list_applications(email),
        "resume": get_resume(email),
        "interviews": get_interviews(email),
        "notifications": get_notifications(email),
        "documents": get_documents(email),
        "profile_status": get_profile_status(email),
        "recommended_jobs": get_recommended_jobs(email),
        "timeline": get_timeline(email),
        "google_user": google_user or {},
    }


def format_timestamp(value: str | None) -> str:
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.strftime("%b %d, %Y")
    except ValueError:
        return value


def get_application_badge_class(status: str) -> str:
    return _badge_class(status)
