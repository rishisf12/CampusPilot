from sqlmodel import Session, select, create_engine, text
from datetime import date
import os

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql+psycopg://campuspilot:campuspilot@postgres:5432/campuspilot')
engine = create_engine(DATABASE_URL)

with Session(engine) as session:
    from models import User, Course
    
    # Get test user
    user = session.exec(select(User).where(User.username == 'testuser')).first()
    if not user:
        print("Test user not found!")
        exit(1)
    
    # Get first 2 courses
    courses = session.exec(select(Course).limit(2)).all()
    print(f"Using courses: {[(c.code, c.id) for c in courses]}")
    
    today = date.today()
    
    # Use raw SQL with correct enum values (uppercase) - inline the values
    for c in courses:
        d1 = date(today.year, today.month, 1)
        d3 = date(today.year, today.month, 3)
        d5 = date(today.year, today.month, 5)
        
        session.execute(text(f"""
            INSERT INTO academic.attendance_record (user_id, course_id, date, status)
            VALUES ({user.id}, {c.id}, '{d1}', 'PRESENT'::public.attendancestatus)
            ON CONFLICT (user_id, course_id, date) DO NOTHING
        """))
        session.execute(text(f"""
            INSERT INTO academic.attendance_record (user_id, course_id, date, status)
            VALUES ({user.id}, {c.id}, '{d3}', 'PRESENT'::public.attendancestatus)
            ON CONFLICT (user_id, course_id, date) DO NOTHING
        """))
        session.execute(text(f"""
            INSERT INTO academic.attendance_record (user_id, course_id, date, status)
            VALUES ({user.id}, {c.id}, '{d5}', 'ABSENT'::public.attendancestatus)
            ON CONFLICT (user_id, course_id, date) DO NOTHING
        """))
    
    session.commit()
    print("Added attendance records via raw SQL")
    print("Done!")