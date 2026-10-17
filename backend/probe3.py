import sys
sys.path.insert(0, "app")
from features.timetable import parser as P
cells = ["CS3010L-AG-CC-3F","IT2002L-JKT O-L102","EC204a/EC204b-PR/KD/SNS-L201","ME3010L-MZA-Batch A-CPPS Lab"]
for c in cells:
    t = P._tokenize_cell(c)
    m = P._merge_room_fragments(t)
    w = P._split_welded_code(m)
    print(f"{c!r}\n   tokenize={t}\n   merged  ={m}\n   welded  ={w}\n   result  ={P.split_slot_cell(c)}")
