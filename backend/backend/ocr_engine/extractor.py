"""OCR + LLM based PDF extraction for timetable and exam seating data."""
import os
import logging
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, time, date
from io import BytesIO

import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import requests

from config import settings

logger = logging.getLogger(__name__)

# Hugging Face Inference API configuration
HF_API_URL = "https://api-inference.huggingface.co/models/"
# Using a lightweight model suitable for structured extraction
DEFAULT_MODEL = "microsoft/phi-3-mini-4k-instruct"
# Alternative: "mistralai/Mistral-7B-Instruct-v0.3" or "google/gemma-2b-it"

# Regex patterns for roll numbers and time
ROLL_PATTERN = re.compile(r'(\d{2}[A-Z]{2,4}\d{3,4})', re.IGNORECASE)
TIME_RANGE_PATTERN = re.compile(r'(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})')
TIME_SINGLE_PATTERN = re.compile(r'(\d{1,2}):(\d{2})')
ROOM_PATTERN = re.compile(r'([A-Z]{1,3}[-\s]?\d{3,4})', re.IGNORECASE)

# Column headers to look for in timetable
TIMETABLE_HEADERS = ['day', 'time', 'subject', 'course', 'room', 'faculty', 'branch', 'semester']
EXAM_HEADERS = ['roll', 'range', 'room', 'date', 'time', 'subject', 'course', 'paper']


def configure_tesseract():
    """Configure tesseract path if needed."""
    # On Windows, tesseract might need explicit path
    if os.name == 'nt':
        possible_paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            r'C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'.format(os.getenv('USERNAME', '')),
        ]
        for path in possible_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                break


def pdf_to_images(pdf_path: Path, dpi: int = 300, poppler_path: Optional[str] = None) -> List[Image.Image]:
    """Convert PDF pages to images."""
    try:
        kwargs = {"dpi": dpi}
        if poppler_path:
            kwargs["poppler_path"] = poppler_path
        elif os.name == 'nt':
            # Try to find poppler on Windows
            possible_paths = [
                r'C:\Program Files\poppler\bin',
                r'C:\Program Files (x86)\poppler\bin',
                r'C:\poppler\bin',
                os.path.expanduser(r'~\poppler\bin'),
            ]
            for path in possible_paths:
                if os.path.exists(os.path.join(path, 'pdftoppm.exe')):
                    kwargs["poppler_path"] = path
                    break
        
        images = convert_from_path(pdf_path, **kwargs)
        logger.info(f"Converted {pdf_path.name} to {len(images)} images")
        return images
    except Exception as e:
        logger.error(f"Failed to convert PDF to images: {e}")
        raise


def extract_text_from_image(image: Image.Image, lang: str = 'eng') -> str:
    """Extract text from image using Tesseract OCR."""
    try:
        # Preprocess image for better OCR
        # Convert to grayscale
        gray = image.convert('L')
        # Increase contrast
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Contrast(gray)
        gray = enhancer.enhance(2.0)
        
        # Extract text with Tesseract
        custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789YOUR_TOKEN_HEREQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.:/-– '
        text = pytesseract.image_to_string(gray, lang=lang, config=custom_config)
        return text
    except Exception as e:
        logger.error(f"OCR failed: {e}")
        return ""


def extract_text_from_pdf(pdf_path: Path, poppler_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Extract text from all pages of a PDF."""
    configure_tesseract()
    images = pdf_to_images(pdf_path, poppler_path=poppler_path)
    
    results = []
    for i, image in enumerate(images):
        text = extract_text_from_image(image)
        results.append({
            'page': i + 1,
            'text': text,
            'image_size': image.size
        })
        logger.info(f"Page {i+1}: extracted {len(text)} characters")
    
    return results


def call_huggingface_llm(prompt: str, model: str = DEFAULT_MODEL, api_token: Optional[str] = None) -> str:
    """Call Hugging Face Inference API."""
    headers = {}
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"
    
    url = f"{HF_API_URL}{model}"
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 1024,
            "temperature": 0.1,
            "top_p": 0.9,
            "do_sample": True,
            "return_full_text": False
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                return result[0].get('generated_text', '')
            return str(result)
        elif response.status_code == 503:
            # Model loading, wait and retry
            logger.warning("Model loading, waiting...")
            import time
            time.sleep(10)
            return call_huggingface_llm(prompt, model, api_token)
        else:
            logger.error(f"HF API error: {response.status_code} - {response.text}")
            return ""
    except Exception as e:
        logger.error(f"HF API call failed: {e}")
        return ""


def build_timetable_prompt(ocr_text: str) -> str:
    """Build prompt for timetable extraction."""
    return f"""You are an expert at extracting structured timetable data from OCR text. 
Extract the timetable information and return ONLY valid JSON.

OCR TEXT:
{ocr_text}

Extract the following fields for each row:
- day: Mon/Tue/Wed/Thu/Fri/Sat/Sun
- start_time: HH:MM format
- end_time: HH:MM format  
- room: Room number (e.g., L-101, CR-201)
- course_code: Course code (e.g., CS301)
- subject: Subject name
- branch: Branch/Program (e.g., CSE, ECE, M.Tech AI)
- semester: Semester number

Return ONLY a JSON array of objects. No explanations.
Example format:
[
  {{"day": "Mon", "start_time": "09:00", "end_time": "10:00", "room": "L-101", "course_code": "CS301", "subject": "Database Systems", "branch": "CSE", "semester": 5}}
]"""


def build_exam_prompt(ocr_text: str) -> str:
    """Build prompt for exam seating extraction."""
    return f"""You are an expert at extracting exam seating data from OCR text.
Extract the exam seating information and return ONLY valid JSON.

OCR TEXT:
{ocr_text}

Extract the following fields for each row:
- roll_range: Roll number range (e.g., "23BCS001-23BCS050" or "23BCS001 to 23BCS050")
- room: Room number (e.g., L-101, CR-201)
- exam_date: Date in YYYY-MM-DD format
- start_time: HH:MM format
- end_time: HH:MM format
- course_code: Course code (e.g., CS301)
- subject: Subject name

Return ONLY a JSON array of objects. No explanations.
Example format:
[
  {{"roll_range": "23BCS001-23BCS050", "room": "L-101", "exam_date": "2026-12-15", "start_time": "09:00", "end_time": "12:00", "course_code": "CS301", "subject": "Database Systems"}}
]"""


def parse_llm_response(response: str) -> List[Dict[str, Any]]:
    """Parse LLM response to extract JSON."""
    # Try to find JSON in the response
    json_match = re.search(r'\[.*\]', response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    
    # Try to find JSON object
    json_match = re.search(r'\{.*\}', response, re.DOTALL)
    if json_match:
        try:
            return [json.loads(json_match.group())]
        except json.JSONDecodeError:
            pass
    
    return []


def extract_timetable_with_llm(pdf_path: Path, hf_token: Optional[str] = None, model: str = DEFAULT_MODEL, poppler_path: Optional[str] = None) -> Dict[str, Any]:
    """Extract timetable data from PDF using OCR + LLM."""
    logger.info(f"Processing timetable PDF: {pdf_path}")
    
    # Extract text via OCR
    ocr_results = extract_text_from_pdf(pdf_path, poppler_path=poppler_path)
    combined_text = "\n\n--- PAGE BREAK ---\n\n".join([r['text'] for r in ocr_results])
    
    # Build prompt and call LLM
    prompt = build_timetable_prompt(combined_text)
    llm_response = call_huggingface_llm(prompt, model=model, api_token=hf_token)
    
    # Parse response
    structured_data = parse_llm_response(llm_response)
    
    # Post-process and validate
    validated_slots = []
    for slot in structured_data:
        validated = validate_timetable_slot(slot)
        if validated:
            validated_slots.append(validated)
    
    return {
        'slots': validated_slots,
        'raw_ocr': ocr_results,
        'llm_response': llm_response,
        'stats': {
            'total_pages': len(ocr_results),
            'slots_extracted': len(validated_slots)
        }
    }


def extract_exam_with_llm(pdf_path: Path, hf_token: Optional[str] = None, model: str = DEFAULT_MODEL, poppler_path: Optional[str] = None) -> Dict[str, Any]:
    """Extract exam seating data from PDF using OCR + LLM."""
    logger.info(f"Processing exam PDF: {pdf_path}")
    
    # Extract text via OCR
    ocr_results = extract_text_from_pdf(pdf_path, poppler_path=poppler_path)
    combined_text = "\n\n--- PAGE BREAK ---\n\n".join([r['text'] for r in ocr_results])
    
    # Build prompt and call LLM
    prompt = build_exam_prompt(combined_text)
    llm_response = call_huggingface_llm(prompt, model=model, api_token=hf_token)
    
    # Parse response
    structured_data = parse_llm_response(llm_response)
    
    # Post-process and validate
    validated_rows = []
    for row in structured_data:
        validated = validate_exam_row(row)
        if validated:
            validated_rows.append(validated)
    
    return {
        'rows': validated_rows,
        'raw_ocr': ocr_results,
        'llm_response': llm_response,
        'stats': {
            'total_pages': len(ocr_results),
            'rows_extracted': len(validated_rows)
        }
    }


def validate_timetable_slot(slot: Dict) -> Optional[Dict]:
    """Validate and normalize timetable slot."""
    required = ['day', 'start_time', 'end_time', 'room', 'course_code']
    for field in required:
        if not slot.get(field):
            return None
    
    # Normalize day
    day = slot['day'][:3].capitalize()
    if day not in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']:
        return None
    
    # Normalize time
    try:
        start = normalize_time(slot['start_time'])
        end = normalize_time(slot['end_time'])
    except:
        return None
    
    # Normalize room
    room = normalize_room(slot['room'])
    
    return {
        'day': day,
        'start_time': start,
        'end_time': end,
        'room': room,
        'course_code': slot['course_code'].upper(),
        'subject': slot.get('subject', ''),
        'branch': slot.get('branch', ''),
        'semester': int(slot.get('semester', 1))
    }


def validate_exam_row(row: Dict) -> Optional[Dict]:
    """Validate and normalize exam row."""
    required = ['roll_range', 'room', 'exam_date']
    for field in required:
        if not row.get(field):
            return None
    
    # Parse roll range
    roll_range = parse_roll_range(row['roll_range'])
    if not roll_range:
        return None
    
    start_prefix, start_num, end_num = roll_range
    
    # Parse date
    try:
        exam_date = datetime.strptime(row['exam_date'], '%Y-%m-%d').date()
    except:
        return None
    
    # Normalize time
    try:
        start_time = normalize_time(row.get('start_time', '09:00'))
        end_time = normalize_time(row.get('end_time', '12:00'))
    except:
        start_time = time(9, 0)
        end_time = time(12, 0)
    
    return {
        'roll_start_prefix': start_prefix,
        'roll_start_num': start_num,
        'roll_end_num': end_num,
        'room': normalize_room(row['room']),
        'exam_date': exam_date,
        'start_time': start_time,
        'end_time': end_time,
        'course_code': row.get('course_code', '').upper(),
        'subject': row.get('subject', '')
    }


def parse_roll_range(range_str: str) -> Optional[tuple]:
    """Parse roll range string into (prefix, start_num, end_num)."""
    # Handle "23BCS001-23BCS050" or "23BCS001 to 23BCS050"
    normalized = range_str.replace(' to ', '-').replace(' TO ', '-').replace('–', '-')
    parts = normalized.split('-')
    if len(parts) != 2:
        return None
    
    start = parse_roll(parts[0].strip())
    end = parse_roll(parts[1].strip())
    
    if not start or not end:
        return None
    
    start_prefix, start_num = start
    end_prefix, end_num = end
    
    if start_prefix != end_prefix:
        return None
    
    return (start_prefix, start_num, end_num)


def parse_roll(roll: str) -> Optional[tuple]:
    """Parse roll number into (prefix, number)."""
    roll = roll.strip().upper()
    match = ROLL_PATTERN.match(roll)
    if match:
        return (match.group(1), int(match.group(2)))
    return None


def normalize_time(time_str: str) -> time:
    """Normalize time string to time object."""
    time_str = time_str.strip().replace('.', ':')
    match = TIME_SINGLE_PATTERN.match(time_str)
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        return time(h % 24, m % 60)
    raise ValueError(f"Invalid time format: {time_str}")


def normalize_room(room: str) -> str:
    """Normalize room string."""
    if not room:
        return ""
    room = room.strip().upper()
    room = re.sub(r'([A-Z]+)\s*(\d+)', r'\1-\2', room)
    room = re.sub(r'\s+', ' ', room).replace(' - ', '-').replace(' -', '-').replace('- ', '-')
    return room


def process_uploaded_pdf(pdf_path: Path, doc_type: str, hf_token: Optional[str] = None, poppler_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Main entry point for processing uploaded PDF.
    doc_type: 'timetable' or 'exam'
    """
    if doc_type == 'timetable':
        return extract_timetable_with_llm(pdf_path, hf_token=hf_token, poppler_path=poppler_path)
    elif doc_type == 'exam':
        return extract_exam_with_llm(pdf_path, hf_token=hf_token, poppler_path=poppler_path)
    else:
        raise ValueError(f"Unknown doc_type: {doc_type}")


if __name__ == "__main__":
    # Test with the downloaded PDFs
    pdf1 = Path(r"C:\Users\Appex\Downloads\MID SEM Indexing 2026-27 (Odd Sem)-print.PDF")
    pdf2 = Path(r"C:\Users\Appex\Downloads\DOC-20260817-WA0002-print.PDF")
    
    # You'll need to set HF_TOKEN environment variable or pass it explicitly
    hf_token = os.getenv("HF_TOKEN")
    
    if pdf1.exists():
        print(f"\n=== Processing {pdf1.name} ===")
        result = process_uploaded_pdf(pdf1, 'exam', hf_token=hf_token)
        print(json.dumps(result, indent=2, default=str))
    
    if pdf2.exists():
        print(f"\n=== Processing {pdf2.name} ===")
        result = process_uploaded_pdf(pdf2, 'timetable', hf_token=hf_token)
        print(json.dumps(result, indent=2, default=str))