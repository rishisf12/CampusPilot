from sqlmodel import Session, select, create_engine
from datetime import time
import os

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql+psycopg://campuspilot:campuspilot@postgres:5432/campuspilot')
engine = create_engine(DATABASE_URL)

with Session(engine) as session:
    from models import TimetableSlot
    
    # Check existing ME semester 5 slots
    existing = session.exec(select(TimetableSlot).where(TimetableSlot.branch_or_program == "ME", TimetableSlot.semester == 5)).all()
    print(f"Found {len(existing)} existing ME semester 5 slots")
    
    # Add ME timetable slots for semester 5
    slots = [
        # Mon
        TimetableSlot(day="Mon", start_time=time(9, 0), end_time=time(10, 0), room="ME-101", course_code="ME301", branch_or_program="ME", semester=5),
        TimetableSlot(day="Mon", start_time=time(10, 0), end_time=time(11, 0), room="ME-102", course_code="ME302", branch_or_program="ME", semester=5),
        TimetableSlot(day="Mon", start_time=time(11, 15), end_time=time(12, 15), room="ME-101", course_code="ME303", branch_or_program="ME", semester=5),
        TimetableSlot(day="Mon", start_time=time(14, 0), end_time=time(15, 0), room="ME-201", course_code="ME304", branch_or_program="ME", semester=5),
        # Tue
        TimetableSlot(day="Tue", start_time=time(9, 0), end_time=time(10, 0), room="ME-102", course_code="ME302", branch_or_program="ME", semester=5),
        TimetableSlot(day="Tue", start_time=time(10, 0), end_time=time(11, 0), room="ME-101", course_code="ME301", branch_or_program="ME", semester=5),
        TimetableSlot(day="Tue", start_time=time(11, 15), end_time=time(12, 15), room="ME-202", course_code="ME303", branch_or_program="ME", semester=5),
        # Wed
        TimetableSlot(day="Wed", start_time=time(9, 0), end_time=time(10, 0), room="ME-101", course_code="ME303", branch_or_program="ME", semester=5),
        TimetableSlot(day="Wed", start_time=time(10, 0), end_time=time(11, 0), room="ME-201", course_code="ME304", branch_or_program="ME", semester=5),
        # Thu
        TimetableSlot(day="Thu", start_time=time(9, 0), end_time=time(10, 0), room="ME-102", course_code="ME301", branch_or_program="ME", semester=5),
        TimetableSlot(day="Thu", start_time=time(10, 0), end_time=time(11, 0), room="ME-101", course_code="ME302", branch_or_program="ME", semester=5),
        # Fri
        TimetableSlot(day="Fri", start_time=time(9, 0), end_time=time(10, 0), room="ME-101", course_code="ME303", branch_or_program="ME", semester=5),
        TimetableSlot(day="Fri", start_time=time(10, 0), end_time=time(11, 0), room="ME-102", course_code="ME301", branch_or_program="ME", semester=5),
    ]
    for s in slots:
        session.add(s)
    session.commit()
    print(f"Added {len(slots)} timetable slots for ME semester 5")
    print("Done!")