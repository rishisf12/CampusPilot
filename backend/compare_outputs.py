"""Compare my parser output against Claude's Excel to identify all gaps."""
import json
from pathlib import Path
from collections import Counter, defaultdict

claude = json.loads(Path(r"F:\UserFolders\Downloads\claude_excel_dump.json").read_text())
mine = json.loads(Path(r"F:\UserFolders\Downloads\my_parser_dump.json").read_text())

claude_entries = claude["all_entries"]

print("=" * 70)
print("COMPARISON: My Parser vs Claude's Excel")
print("=" * 70)
print(f"Claude entries: {len(claude_entries)}")
print(f"My entries:     {len(mine)}")
print(f"Gap:            {len(claude_entries) - len(mine)} fewer slots in mine")
print()

# 1. Branch distribution comparison
print("--- 1. BRANCH DISTRIBUTION ---")
claude_branches = Counter(e["Branch"] for e in claude_entries)
my_branches = Counter(e["Branch"] for e in mine)
all_branches = sorted(set(list(claude_branches.keys()) + list(my_branches.keys())))
print(f"{'Branch':<15} {'Claude':<10} {'Mine':<10} {'Gap':<10}")
for b in all_branches:
    c = claude_branches.get(b, 0)
    m = my_branches.get(b, 0)
    print(f"{b:<15} {c:<10} {m:<10} {c-m:<10}")
print()

# 2. Semester distribution
print("--- 2. SEMESTER DISTRIBUTION ---")
claude_sems = Counter(str(e["Semester"]) for e in claude_entries)
my_sems = Counter(str(e["Semester"]) for e in mine)
all_sems = sorted(set(list(claude_sems.keys()) + list(my_sems.keys())))
print(f"{'Semester':<10} {'Claude':<10} {'Mine':<10} {'Gap':<10}")
for s in all_sems:
    c = claude_sems.get(s, 0)
    m = my_sems.get(s, 0)
    print(f"{s:<10} {c:<10} {m:<10} {c-m:<10}")
print()

# 3. Day distribution
print("--- 3. DAY DISTRIBUTION ---")
claude_days = Counter(e["Day"] for e in claude_entries)
my_days = Counter(e["Day"] for e in mine)
all_days = sorted(set(list(claude_days.keys()) + list(my_days.keys())))
for d in all_days:
    c = claude_days.get(d, 0)
    m = my_days.get(d, 0)
    print(f"{d:<15} Claude={c:<6} Mine={m:<6} Gap={c-m}")
print()

# 4. Course code comparison - find courses Claude has that I don't
print("--- 4. COURSE CODES MISSING FROM MINE ---")
claude_courses = set(e["Course Code"] for e in claude_entries if e["Course Code"])
my_courses = set(e["Course Code"] for e in mine if e["Course Code"])
missing = claude_courses - my_courses
extra = my_courses - claude_courses
print(f"Claude unique courses: {len(claude_courses)}")
print(f"My unique courses:     {len(my_courses)}")
print(f"Missing from mine:     {len(missing)}")
print(f"Extra in mine:         {len(extra)}")
print()
if missing:
    print("First 30 missing courses:")
    for c in sorted(missing)[:30]:
        print(f"  {c}")
print()

# 5. Room format comparison
print("--- 5. ROOM FORMAT COMPARISON ---")
claude_rooms = Counter(e["Room"] for e in claude_entries if e["Room"])
my_rooms = Counter(e["Room"] for e in mine if e["Room"])
print("Claude room samples:", list(claude_rooms.keys())[:15])
print("My room samples:    ", list(my_rooms.keys())[:15])
print()

# 6. Instructor comparison
print("--- 6. INSTRUCTOR COMPARISON ---")
claude_inst = Counter(e["Instructor"] for e in claude_entries if e["Instructor"])
my_inst = Counter(e["Instructor"] for e in mine if e["Instructor"])
missing_inst = set(claude_inst.keys()) - set(my_inst.keys())
print(f"Claude instructors: {len(claude_inst)}")
print(f"My instructors:     {len(my_inst)}")
print(f"Missing from mine:  {len(missing_inst)}")
if missing_inst:
    print("Missing instructors:", sorted(missing_inst)[:20])
print()

# 7. Time format
print("--- 7. TIME FORMAT ---")
print("Claude time samples:", [e["Time"] for e in claude_entries[:5]])
print("My time samples:   ", [e["Time"] for e in mine[:5]])
print()

# 8. Remarks
print("--- 8. REMARKS ---")
claude_remarks = Counter(e["Remarks"] for e in claude_entries if e["Remarks"])
my_remarks = Counter(e["Remarks"] for e in mine if e["Remarks"])
print("Claude remarks:", dict(claude_remarks))
print("My remarks:   ", dict(my_remarks))
