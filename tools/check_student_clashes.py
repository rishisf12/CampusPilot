"""
Exercise the personal exam-clash detector against the real seating index.

Uses the signed-in student's own profile so the result matches exactly what the
Quick Roll Lookup shows, then sweeps rolls to see how noisy the detector is.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend" / "backend"))

from sqlmodel import Session, select  # noqa: E402

from core.database import engine  # noqa: E402
from models import ExamSeating, User, UserProfile  # noqa: E402
from features.exam.clash import (  # noqa: E402
    clash_summary,
    collect_student_exams,
    detect_student_exam_clashes,
)
from features.profile.service import profile_to_filter  # noqa: E402


def profile_for(session, roll):
    user = session.exec(select(User).where(User.roll_number == roll)).first()
    if not user:
        return None
    profile = session.exec(select(UserProfile).where(UserProfile.user_id == user.id)).first()
    return profile_to_filter(profile) if profile else None


def main() -> int:
    with Session(engine) as session:
        total = len(session.exec(select(ExamSeating)).all())
        print(f"seating rows in database : {total}")
        if not total:
            print("No seating data - upload the seating index first.")
            return 1

        registered = [
            row.roll_number
            for row in session.exec(select(User)).all()
            if row.roll_number
        ]
        print(f"registered rolls         : {registered}\n")

        print("--- registered students ---")
        for roll in registered:
            profile = profile_for(session, roll)
            exams = collect_student_exams(session, roll, profile)
            clashes = detect_student_exam_clashes(session, roll, profile)
            who = f"{profile['branch']} sem {profile['semester']} extras={profile['elective_codes']}"
            print(f"  {roll}  ({who})")
            for exam in exams:
                rooms = "/".join(exam["rooms"]) or "-"
                print(f"      {exam['date']} {exam['start_time']}-{exam['end_time']} "
                      f"{exam['course_code']:<9} @{rooms}"
                      f"{'  [extra]' if exam['is_extra'] else ''}")
            if clashes:
                for clash in clashes:
                    codes = " vs ".join(
                        f"{c['course_code']}({'/'.join(c['rooms']) or '-'})"
                        for c in clash["courses"]
                    )
                    print(f"    !! CLASH {clash['date']} {clash['day'][:3]} "
                          f"{clash['start_time']}-{clash['end_time']}: {codes}")
            else:
                print("    no clashes")

        # Sweep every roll in the index to check the false-positive rate.
        print("\n--- sweeping all rolls in the index (profile-filtered) ---")
        rows = session.exec(select(ExamSeating)).all()
        rolls = set()
        for row in rows:
            rolls.add(f"{row.roll_start_prefix}{row.roll_start_num:03d}")
            rolls.add(f"{row.roll_start_prefix}{row.roll_end_num:03d}")
        rolls = sorted(rolls)

        # A representative profile: CSE A, sem 5.
        profile = {"branch": "CSE A", "semester": 5, "elective_codes": []}
        with_clash = 0
        max_clashes = 0
        worst = None
        exam_total = 0
        for roll in rolls:
            exams = collect_student_exams(session, roll, profile)
            clashes = detect_student_exam_clashes(session, roll, profile)
            exam_total += len(exams)
            if clashes:
                with_clash += 1
                if len(clashes) > max_clashes:
                    max_clashes, worst = len(clashes), roll

        print(f"  rolls checked        : {len(rolls)}")
        print(f"  exams resolved/roll  : {exam_total / max(len(rolls), 1):.1f} average")
        print(f"  rolls with a clash   : {with_clash} ({100 * with_clash / max(len(rolls), 1):.0f}%)")
        print(f"  worst roll           : {worst} with {max_clashes}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())