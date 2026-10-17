import sys
sys.path.insert(0, "app")
from features.timetable import reinforcement
m = reinforcement.get_reinforcement_model()
print("patterns loaded:", len(getattr(m, "patterns", []) or []))
for cell in ["CS3010L-AG-CC-3F", "IT2002L-JKT O-L102", "EC204a/EC204b-PR/KD/SNS-L201", "ME3010L-MZA-Batch A-CPPS Lab"]:
    out = m.apply(cell)
    flag = "  CHANGED" if out != cell else ""
    print(f"{cell!r}\n  -> {out!r}{flag}")
