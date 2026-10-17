import sys
sys.path.insert(0, "app")
import re
from features.timetable import parser as P
for c in ["CS3010L","IT2002L","ME3010L","EC204A","EC204B","ME3010A","EC5C01","ME8016"]:
    print(f"{c:9} _is_course={P._is_course(c)!s:5} labL={bool(re.match(r'^[A-Z]{2,4}[0-9]{3,4}L$', c))} stripL={re.sub(r'^([A-Z]{2,4}[0-9]{3,4})[A-Z]$', chr(92)+chr(49), c)}")
