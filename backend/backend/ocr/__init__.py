"""OCR Engine Package for CampusPilot.

This package provides OCR + LLM based PDF extraction capabilities
for timetable and exam seating data extraction.
"""

from .extractor import (
    process_uploaded_pdf,
    extract_text_from_pdf,
    extract_timetable_with_llm,
    extract_exam_with_llm,
)

__all__ = [
    "extract_exam_with_llm",
    "extract_text_from_pdf",
    "extract_timetable_with_llm",
    "process_uploaded_pdf",
]