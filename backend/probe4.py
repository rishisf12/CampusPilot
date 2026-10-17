import sys
sys.path.insert(0, "app")
from features.timetable import parser as NEW
from features.timetable import parser_prev as OLD
cells = ["CS3010L-AG-CC-3F","IT2002L-JKT O-L102","EC204a/EC204b-PR/KD/SNS-L201","ME3010L-MZA-Batch A-CPPS Lab","SM3012L-Batch A-SA-CPPS Lab"]
for c in cells:
    print(f"{c!r}")
    print(f"   OLD welded={OLD._split_welded_code(OLD._merge_room_fragments(OLD._tokenize_cell(c)))}")
    print(f"   NEW welded={NEW._split_welded_code(NEW._merge_room_fragments(NEW._tokenize_cell(c)))}")
    try: o = OLD.split_slot_cell(c)
    except Exception as e: o = ("ERR", type(e).__name__, "")
    print(f"   OLD result={o}")
    print(f"   NEW result={NEW.split_slot_cell(c)}")
