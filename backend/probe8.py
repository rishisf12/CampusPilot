import sys
sys.path.insert(0, "app")
sys.path.insert(0, "app/tests")
from features.timetable.parser import parse_day_section_timetable
import importlib.util
spec = importlib.util.spec_from_file_location("tg", "app/tests/test_timetable_grid.py")
tg = importlib.util.module_from_spec(spec); spec.loader.exec_module(tg)
slots, warns = parse_day_section_timetable([tg.DAY_SECTION_TABLE])
print("warnings:", warns, "| count:", len(slots))
for s in slots:
    print(f"  {s['day']} {s['start_time']}-{s['end_time']} {s['course_code']:9} {str(s['instructor']):6} {s['room']}")
