import sys
sys.path.insert(0, "app")
from features.timetable.parser import parse_day_section_timetable
from tests.test_timetable_grid import DAY_SECTION_TABLE
slots, warns = parse_day_section_timetable([DAY_SECTION_TABLE])
print("warnings:", warns, "count:", len(slots))
for s in slots:
    print(f"  {s['day']} {s['start_time']}-{s['end_time']} {s['course_code']:9} {s['instructor']:6} {s['room']}")
