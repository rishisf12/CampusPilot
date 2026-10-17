import sys, traceback
sys.path.insert(0, "app")
from sqlmodel import Session, select
from core.database import engine
from models import AttendanceRecord

with Session(engine) as s:
    try:
        rows = s.exec(select(AttendanceRecord)).all()
        print("READ OK, rows:", len(rows))
        print("statuses:", [(r.id, r.status) for r in rows][:8])
    except Exception as e:
        print("READ FAILED:", type(e).__name__)
        print(str(e)[:600])
