from io import BytesIO
from typing import Optional

from pdfminer.high_level import extract_text as pdf_extract
from docx import Document


def pdf_to_text(data: bytes) -> str:
    with BytesIO(data) as bio:
        return pdf_extract(bio)


def docx_to_text(data: bytes) -> str:
    with BytesIO(data) as bio:
        doc = Document(bio)
        return "\n".join(p.text for p in doc.paragraphs)
