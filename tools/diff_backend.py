"""Diff the session's backend files against the backend on disk."""
import difflib
from pathlib import Path

ROOT = Path(r"C:\Users\Appex\Documents\Default Project\CampusPilot")
SESSION_BACKEND = ROOT / "tools" / "session_extract" / "backend"
DISK_BACKEND = ROOT / "backend" / "backend"

if not SESSION_BACKEND.exists():
    raise SystemExit("run a backend replay first")

print(f"{'file':<28} {'session':>9} {'disk':>9}  status")
print("-" * 70)
for session_file in sorted(SESSION_BACKEND.rglob("*.py")):
    relative = session_file.relative_to(SESSION_BACKEND)
    disk_file = DISK_BACKEND / relative
    session_text = session_file.read_text(encoding="utf-8", errors="replace")
    if disk_file.exists():
        disk_text = disk_file.read_text(encoding="utf-8", errors="replace")
        status = "same" if session_text == disk_text else "DIFFERENT"
    else:
        disk_text = ""
        status = "MISSING ON DISK"
    print(f"{str(relative):<28} {len(session_text):>9} {len(disk_text):>9}  {status}")

# Which endpoints does the session's backend declare that disk does not?
print("\n--- endpoints in session attendance/auth/timetable routes ---")
import re

pattern = re.compile(r'@router\.(get|post|put|delete|patch)\(\s*"([^"]+)"')
for name in ("attendance.py", "auth.py", "timetable.py", "exam.py", "profile.py"):
    for base in (SESSION_BACKEND / "routes", DISK_BACKEND / "routes"):
        target = base / name
        if not target.exists():
            continue
        text = target.read_text(encoding="utf-8", errors="replace")
        found = sorted({f"{m.upper()} {p}" for m, p in pattern.findall(text)})
        label = "session" if base == SESSION_BACKEND / "routes" else "disk   "
        print(f"\n{label} {name}:")
        for item in found:
            print(f"    {item}")