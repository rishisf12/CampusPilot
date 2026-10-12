from sqlmodel import Session, select, create_engine
from datetime import date
import os

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql+psycopg://campuspilot:campuspilot@postgres:5432/campuspilot')
engine = create_engine(DATABASE_URL)

with Session(engine) as session:
    from models import User, Course, AttendanceRecord, AttendanceStatus
    
    # Get test user
    user = session.exec(select(User).where(User.username == 'testuser')).first()
    if not user:
        print("Test user not found!")
        exit(1)
    
    # Get first 2 courses
    courses = session.exec(select(Course).limit(2)).all()
    print(f"Using courses: {[(c.code, c.id) for c in courses]}")
    
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
    session.commit()
    print(f"Added {len(records)} attendance records")
    print("Done!")