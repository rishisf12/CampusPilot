"""Show exactly which index rows contain a given roll, and why they collide."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend" / "backend"))

from sqlmodel import Session, select  # noqa: E402

from core.database import engine  # noqa: E402
from models import ExamSeating, User, UserProfile  # noqa: E402
from features.exam.clash import collect_student_exams  # noqa: E402
from features.exam.lookup import find_candidate_rows  # noqa: E402

ROLL = sys.argv[1] if len(sys.argv) > 1 else "23BCS125"


def main() -> int:
    with Session(engine) as session:
        user = session.exec(select(User).where(User.roll_number == ROLL)).first()
        if user:
            profile = session.exec(
                select(UserProfile).where(UserProfile.user_id == user.id)
            ).first()
            print(f"registered student: {user.username} "
                  f"branch={profile.branch} sem={profile.semester} "
                  f"electives={profile.elective_codes}")
        else:
            print(f"no registered user with roll {ROLL}")

        rows = find_candidate_rows(session, ROLL)
        print(f"\nraw index rows containing {ROLL}: {len(rows)}\n")
        print(f"{'course':<10} {'date':<12} {'time':<14} {'room':<9} {'branch':<8} sem extra")
        for row in sorted(rows, key=lambda r: (r.seating_date, r.start_time, r.course_code)):
            print(f"{row.course_code:<10} {str(row.seating_date):<12} "
                  f"{row.start_time.strftime('%H:%M')}-{row.end_time.strftime('%H:%M'):<8} "
                  f"{row.room:<9} {str(row.branch):<8} {row.semester} "
                  f"{'yes' if row.is_extra else ''}")

        exams = collect_student_exams(session, ROLL)
        print(f"\nde-duplicated exams: {len(exams)}")
        for exam in exams:
            print(f"  {exam['seating_date']} "
                  f"{exam['start_time'].strftime('%H:%M')}-{exam['end_time'].strftime('%H:%M')} "
                  f"{exam['course_code']:<10} sem={exam['semester']} "
                  f"branch={exam['branch']} extra={exam['is_extra']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())