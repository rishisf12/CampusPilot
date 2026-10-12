from sqlmodel import Session, select, create_engine, text
from datetime import time
import os

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql+psycopg://campuspilot:campuspilot@postgres:5432/campuspilot')
engine = create_engine(DATABASE_URL)

with Session(engine) as session:
    from models import TimetableSlot
    
    # Check existing slots for CSE semester 5
    existing = session.exec(select(TimetableSlot).where(TimetableSlot.branch_or_program == "CSE", TimetableSlot.semester == 5)).all()
    if existing:
        print(f"Found {len(existing)} existing CSE semester 5 slots")
    else:
        print("No existing CSE semester 5 slots, adding...")
    
    # Add timetable slots for CSE semester 5
    slots = [
        # Mon
        TimetableSlot(day="Mon", start_time=time(9, 0), end_time=time(10, 0), room="L-101", course_code="CS301", branch_or_program="CSE", semester=5),
        TimetableSlot(day="Mon", start_time=time(10, 0), end_time=time(11, 0), room="L-102", course_code="CS302", branch_or_program="CSE", semester=5),
        TimetableSlot(day="Mon", start_time=time(11, 15), end_time=time(12, 15), room="L-101", course_code="CS303", branch_or_program="CSE", semester=5),
        TimetableSlot(day="Mon", start_time=time(14, 0), end_time=time(15, 0), room="CR-201", course_code="CS304", branch_or_program="CSE", semester=5),
        # Tue
        TimetableSlot(day="Tue", start_time=time(9, 0), end_time=time(10, 0), room="L-102", course_code="CS302", branch_or_program="CSE", semester=5),
        TimetableSlot(day="Tue", start_time=time(10, 0), end_time=time(11, 0), room="L-101", course_code="CS301", branch_or_program="CSE", semester=5),
        TimetableSlot(day="Tue", start_time=time(11, 15), end_time=time(12, 15), room="L-201", course_code="CS303", branch_or_program="CSE", semester=5),
        # Wed
        TimetableSlot(day="Wed", start_time=time(9, 0), end_time=time(10, 0), room="L-101", course_code="CS303", branch_or_program="CSE", semester=5),
        TimetableSlot(day="Wed", start_time=time(10, 0), end_time=time(11, 0), room="CR-201", course_code="CS304", branch_or_program="CSE", semester=5),
        # Thu
        TimetableSlot(day="Thu", start_time=time(9, 0), end_time=time(10, 0), room="L-102", course_code="CS301", branch_or_program="CSE", semester=5),
        TimetableSlot(day="Thu", start_time=time(10, 0), end_time=time(11, 0), room="L-101", course_code="CS302", branch_or_program="CSE", semester=5),
        # Fri
        TimetableSlot(day="Fri", start_time=time(9, 0), end_time=time(10, 0), room="L-101", course_code="CS303", branch_or_program="CSE", semester=5),
        TimetableSlot(day="Fri", start_time=time(10, 0), end_time=time(11, 0), room="L-102", course_code="CS301", branch_or_program="CSE", semester=5),
    ]
    for s in slots:
        session.add(s)
    session.commit()
    print(f"Added {len(slots)} timetable slots for CSE semester 5")
    print("Done!")