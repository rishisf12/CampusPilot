import sys
sys.path.insert(0, "app")
from features.timetable import parser as P
cells = ["CS3010L-AG-CC-3F","IT2002L-JKT O-L102","ME3010L-MZA-Batch A-CPPS Lab","SM3012L-Batch A-SA-CPPS Lab","ME3011L-SKC-Batch A - HMT Lab","SM3010L-ARR-Batch A -CC2- GF","EC204a/EC204b-PR/KD/SNS-L201","ME3011L-A","EC203a/EC203b-SKT-L201"]
for c in cells:
    print(f"{c!r}\n   tok={P._tokenize_cell(c)}\n   ->  {P.split_slot_cell(c)}")
