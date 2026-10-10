"""Print the rolls that the detector flags, with their full exam lists."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend" / "backend"))

from sqlmodel import Session, select  # noqa: E402

from core.database import engine  # noqa: E402
from models import ExamSeating  # noqa: E402
from features.exam.clash import collect_student_exams, detect_student_exam_clashes  # noqa: E402

PROFILE = {"branch": "CSE A", "semester": 5, "elective_codes": []}


def main() -> int:
    with Session(engine) as session:
        rows = session.exec(select(ExamSeating)).all()
        rolls = sorted(
            {f"{r.roll_start_prefix}{r.roll_start_num:03d}" for r in rows}
            | {f"{r.roll_start_prefix}{r.roll_end_num:03d}" for r in rows}
        )

        flagged = 0
        for roll in rolls:
            clashes = detect_student_exam_clashes(session, roll, PROFILE)
            if not clashes:
                continue
            flagged += 1
            exams = collect_student_exams(session, roll, PROFILE)
            print(f"--- {roll}: {len(exams)} exam(s) ---")
            for exam in exams:
                rooms = "/".join(exam["rooms"]) or "-"
                print(f"      {exam['date']}  {exam['start_time']}-{exam['end_time']}  "
                      f"{exam['course_code']:<9} @ {rooms}")
            for clash in clashes:
                codes = " vs ".join(c["course_code"] for c in clash["courses"])
                print(f"    CLASH  {clash['date']} {clash['day'][:3]} "
                      f"{clash['start_time']}-{clash['end_time']}: {codes}")
            print()

        print(f"total flagged: {flagged} of {len(rolls)} roll(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())