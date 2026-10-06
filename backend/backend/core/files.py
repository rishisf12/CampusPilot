"""Runtime file-prompting utilities: validate, save, and raise clear HTTP errors."""
import os
import shutil
from pathlib import Path
from fastapi import HTTPException, UploadFile
from core.config import settings

UPLOAD_DIR = Path(__file__).resolve().parents[1] / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {ext.strip().lower() for ext in settings.allowed_extensions.split(",")}
MAX_BYTES = settings.max_upload_mb * 1024 * 1024


def validate_upload(file: UploadFile, expected: str) -> None:
    """
    Validate extension, MIME type, and size.
    Raises HTTPException 400 with a clear message if invalid.
    """
    # Extension
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Expected {expected} ({', '.join(sorted(ALLOWED_EXTENSIONS))}), got {ext}"
        )

    # Size (peek at content-length header if available)
    content_length = file.headers.get("content-length")
    if content_length and int(content_length) > MAX_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large: {int(content_length) / 1024 / 1024:.1f} MB > {settings.max_upload_mb} MB limit"
        )

    # MIME type (basic check)
    allowed_mimes = {
        ".pdf": "application/pdf",
        ".csv": "text/csv",
    }
    expected_mime = allowed_mimes.get(ext)
    if expected_mime and file.content_type != expected_mime:
        # Some clients send application/octet-stream; warn but don't block
        pass


def save_upload(file: UploadFile, prefix: str = "upload") -> Path:
    """
    Save upload to /uploads with a safe filename.
    Returns the saved Path.
    """
    import uuid
    from datetime import datetime

    ext = Path(file.filename).suffix.lower()
    safe_name = f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
    dest = UPLOAD_DIR / safe_name

    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    # Verify size after save
    size = dest.stat().st_size

    # An empty file is almost always a failed download, and every parser then
    # reports it in its own unhelpful terms ("No /Root object! - Is this really
    # a PDF?"), so catch it here with something the user can act on.
    if size == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=(
                f"'{file.filename}' is empty (0 bytes), so it cannot be read. "
                "The download most likely failed - re-download the file and upload it again."
            ),
        )

    if size > MAX_BYTES:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="File exceeds size limit after upload")

    return dest


def read_csv_fallback(path: Path) -> list[dict]:
    """Read CSV with expected timetable columns."""
    import csv
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def save_upload_from_bytes(data: bytes, original_filename: str, prefix: str = "upload") -> Path:
    """
    Save raw bytes to /uploads with a safe filename.
    Returns the saved Path.
    """
    import uuid
    from datetime import datetime

    ext = Path(original_filename).suffix.lower()
    safe_name = f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
    dest = UPLOAD_DIR / safe_name

    with dest.open("wb") as out:
        out.write(data)

    size = dest.stat().st_size
    if size == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Empty attachment")
    if size > MAX_BYTES:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Attachment exceeds size limit")

    return dest