"""Run my parser on the PDF and dump results for comparison."""
import json
import sys
sys.path.insert(0, r"C:\Users\Appex\Documents\Default Project\CampusPilot\backend\app")

from pathlib import Path
from features.timetable.parser import parse_timetable_file

pdf_path = Path(r"F:\UserFolders\Downloads\DOC-20260817-WA0002-print.PDF")
result = parse_timetable_file(pdf_path, is_csv=False)

slots = result["slots"]
print(f"My parser: {len(slots)} slots")
print(f"Warnings: {len(result.get('warnings', []))}")

# Normalize to same shape as Claude's All Entries
# Claude: Semester, Branch, Day, Course Code, Instructor, Room, Time, Remarks
# Mine: day, start_time, end_time, room, course_code, instructor, branch_or_program, semester, remarks
normalized = []
for s in slots:
    normalized.append({
        "Semester": s.get("semester"),
        "Branch": s.get("branch_or_program"),
        "Day": s.get("day"),
        "Course Code": s.get("course_code"),
        "Instructor": s.get("instructor"),
        "Room": s.get("room"),
        "Time": f"{s.get('start_time')}-{s.get('end_time')}" if s.get('start_time') else None,
        "Remarks": s.get("remarks"),
    })

out_path = Path(r"F:\UserFolders\Downloads\my_parser_dump.json")
out_path.write_text(json.dumps(normalized, indent=2, default=str), encoding="utf-8")

print(f"Saved {len(normalized)} slots to {out_path}")
print("\nFirst 10 slots:")
for s in normalized[:10]:
    print(" ", s)
