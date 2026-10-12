from sqlmodel import Session, select, create_engine
from datetime import date, time
import os

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql+psycopg://campuspilot:campuspilot@postgres:5432/campuspilot')
engine = create_engine(DATABASE_URL)

with Session(engine) as session:
    from models import User, UserProfile, Course, AttendanceRecord, AttendanceStatus, TimetableSlot, ExamSeating
    
    # Get test user
    user = session.exec(select(User).where(User.username == 'testuser')).first()
    if not user:
        print("Test user not found!")
        exit(1)
    
    print(f"User: {user.username} (id={user.id})")
    
    # Get courses
    courses = session.exec(select(Course)).all()
    print(f"Found {len(courses)} courses")
    for c in courses:
        print(f"  {c.code} (id={c.id})")
    
    # Add attendance records for the test user
    today = date.today()
    records = [
        AttendanceRecord(user_id=user.id, course_id=courses[0].id, date=date(today.year, today.month, 1), status=AttendanceStatus.PRESENT),
        AttendanceRecord(user_id=user.id, course_id=courses[0].id, date=date(today.year, today.month, 3), status=AttendanceStatus.PRESENT),
        AttendanceRecord(user_id=user.id, course_id=courses[0].id, date=date(today.year, today.month, 5), status=AttendanceStatus.ABSENT),
        AttendanceRecord(user_id=user.id, course_id=courses[1].id, date=date(today.year, today.month, 2), status=AttendanceStatus.PRESENT),
        AttendanceRecord(user_id=user.id, course_id=courses[1].id, date=date(today.year, today.month, 4), status=AttendanceStatus.ABSENT),
    ]
    for r in records:
        session.add(r)
    print(f"Added {len(records)} attendance records")
    
    # Add exam seating
    exams = [
        ExamSeating(roll_start_prefix="23BCS", roll_start_num=1, roll_end_num=50, room="L-101", exam_date=date(2026, 12, 15), start_time=time(9, 0), end_time=time(12, 0), course_code="CS301"),
        ExamSeating(roll_start_prefix="23BCS", roll_start_num=51, roll_end_num=100, room="L-102", exam_date=date(2026, 12, 15), start_time=time(9, 0), end_time=time(12, 0), course_code="CS301"),
        ExamSeating(roll_start_prefix="23BCS", roll_start_num=1, roll_end_num=100, room="CR-201", exam_date=date(2026, 12, 17), start_time=time(9, 0), end_time=time(12, 0), course_code="CS302"),
    ]
    for e in exams:
        session.add(e)
    print(f"Added {len(exams)} exam seating records")
    
    session.commit()
    print("Done!")