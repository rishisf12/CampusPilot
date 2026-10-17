import sys
sys.path.insert(0, "app")
from features.timetable import parser as NEW
from features.timetable import parser_prev as OLD
cells = ["CS3010L-AG-CC-3F","IT2002L-JKT O-L102","ME3010L-MZA-Batch A-CPPS Lab","SM3012L-Batch A-SA-CPPS Lab"]
for c in cells:
    print(f"{c!r}")
    print(f"   OLD tok={OLD._tokenize_cell(c)}")
    print(f"   NEW tok={NEW._tokenize_cell(c)}")
