import os
import uuid
from fastapi import UploadFile

UPLOAD_FOLDER = "uploads"

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".docx"
}


def save_resume(file: UploadFile):

   
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    
    extension = os.path.splitext(file.filename)[1].lower()

    
    if extension not in ALLOWED_EXTENSIONS:
        raise Exception("Only PDF and DOCX files are allowed.")

    
    filename = f"{uuid.uuid4()}{extension}"

    filepath = os.path.join(
        UPLOAD_FOLDER,
        filename
    )

    
    with open(filepath, "wb") as buffer:
        buffer.write(file.file.read())

    return filepath