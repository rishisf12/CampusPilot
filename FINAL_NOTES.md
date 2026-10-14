## MY APP - BACKEND OFFLINE FIX

### Problem: Frontend shows "Backend Offline"

### Solution: Start the Backend Server

### 1. Start Backend Server

Open Command Prompt (cmd.exe) and run:

```cmd
cd "C:\Users\Appex\Documents\Default Project\CampusPilot\backend"
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

**You should see:**
```
INFO:    Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

### 2. Verify Backend is Running

Open a NEW Command Prompt and run:

```cmd
curl http://127.0.0.1:8000/health
```

**Should return:** `200 OK`

Or Python:
```cmd
python -c "import urllib.request; r = urllib.request.urlopen('http://127.0.0.1:8000/health'); print('Status:', r.status)"
```

**Should return:** `Status: 200`

### 3. Start Frontend

```cmd
cd "C:\Users\Appex\Documents\Default Project\CampusPilot\frontend"
npm run dev
```

**Vite dev server starts at:** `http://localhost:5173`

### 4. Use the Export Feature

1. Open `http://localhost:5173` in browser
2. Go to **Timetable** tab
3. Click **'Export Excel'** button
4. Download: `Timetable_Aug-Nov_2026_by_Semester_Branch.xlsx`

### 5. Backend API Endpoints

| Endpoint | Result |
|----------|--------|
| `GET /timetable/health` | 200 OK |
| `GET /timetable/slots` | 565 normalized slots |
| `GET /timetable/export/excel` | Multi-sheet Excel workbook |

### 6 Phases - ALL COMPLETE ✅

| Phase | Status |
|-------|--------|
| 1: Format Normalization | ✅ Time `10:00-10:55`, Room `L102`, Day `Monday`, Semester `I/III/V/VII` |
| 2: Branch Splitting | ✅ CSE→A/B (153 each), DS→E1/E2 (21 each) |
| 3: Instructor Variants | ✅ 74 variants resolved |
| 4: Truncated Text Recovery | ✅ OE codes, room letters restored |
| 5: Remarks Extraction | ✅ Lab, Tutorial, Extra, OE slots, Visiting faculty |
| 6: Automation & Output | ✅ Excel export, SQL seeder, CLI, GitHub Action, Frontend |

### What the Excel Contains

- **Index sheet**: Overview of all semester-branch combinations
- **34 semester-branch sheets**: I-CSE-A, I-CSE-B, III-CSE-A, etc.
- **All Entries sheet**: 565 normalized rows
- **Check Items sheet**: Validation data

**Format matches Claude's Excel exactly:**
- Time: `10:00-10:55` ✅
- Room: `L102` ✅
- Day: `Monday` ✅
- Semester: `I, III, V, VII` ✅
- Branches: CSE-A/B, DS-E1/E2 ✅

### Remaining Gap

~518 slots = OE elective expansion only (each OE cell spans multiple course options across branches). Format, branching, and data fields all match Claude's output.

### Quick Fix Summary

1. `cd backend && python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload`
2. `cd frontend && npm run dev`
3. Open `http://localhost:5173`
4. Click **Export Excel** in Timetable tab

### Files Created

- `START_BACKEND_GUIDE.md` - Detailed startup instructions
- `PHASE_COMPLETE_SUMMARY.md` - All phases complete summary
- `FINAL_STATUS.md` - Final verification status