import fitz  # PyMuPDF
from io import BytesIO
from docx import Document


def extract_pdf_text(file_bytes: bytes) -> str:
    """
    Extract text from a PDF file.
    """
    text = ""

    pdf = fitz.open(stream=file_bytes, filetype="pdf")

    for page in pdf:
        text += page.get_text()

    pdf.close()

    return text.strip()


def extract_docx_text(file_bytes: bytes) -> str:
    """
    Extract text from a DOCX file.
    """
    document = Document(BytesIO(file_bytes))

    text = []

    for paragraph in document.paragraphs:
        text.append(paragraph.text)

    return "\n".join(text).strip()


def extract_resume_text(filename: str, file_bytes: bytes) -> str:
    """
    Detect file type and extract text.
    """

    filename = filename.lower()

    if filename.endswith(".pdf"):
        return extract_pdf_text(file_bytes)

    elif filename.endswith(".docx"):
        return extract_docx_text(file_bytes)

    else:
        raise Exception("Unsupported file type")