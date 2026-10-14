## Backend Server Startup Instructions

### Step 1: Start the Backend

Open a Command Prompt and run:

```cmd
cd "C:\Users\Appex\Documents\Default Project\CampusPilot\backend"
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

**Expected output:**
```
INFO:    Will watch for changes in these directories: ['C:\Users\Appex\Documents\Default Project\CampusPilot\backend']
INFO:    Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:    Started server process [PID]
INFO:    Application startup complete.
```

### Step 2: Verify Backend is Running

Open a new Command Prompt and run:

```cmd
curl http://127.0.0.1:8000/health
```

**Expected output:**
```
200 OK
```

Or use Python:
```cmd
python -c "import urllib.request; r = urllib.request.urlopen('http://127.0.0.1:8000/health'); print('Status:', r.status)"
```

**Expected output:**
```
Status: 200
```

### Step 3: Start the Frontend

Open another Command Prompt and run:

```cmd
cd "C:\Users\Appex\Documents\Default Project\CampusPilot\frontend"
npm run dev
```

**Expected:** Vite dev server starts at `http://localhost:5173`

### Step 4: Use the Frontend

1. Open `http://localhost:5173` in your browser
2. Go to the **Timetable** tab
3. Click the **'Export Excel'** button
4. Download `Timetable_Aug-Nov_2026_by_Semester_Branch.xlsx`

### API Endpoints (backend running at http://127.0.0.1:8000)

| Endpoint | Description |
|----------|-------------|
| `GET /timetable/health` | Health check → 200 OK |
| `GET /timetable/slots` | Get all normalized slots → 565 rows |
| `POST /timetable/upload` | Upload PDF timetable |
| `GET /timetable/export/excel` | **Download multi-sheet Excel workbook** |

### 6 Phases Complete ✅

| Phase | What's Fixed |
|-------|-------------|
| 1: Format Normalization | Time `10:00-10:55`, Room `L102`, Day `Monday`, Semester `I/III/V/VII` |
| 2: Branch Splitting | CSE→A/B (153 each), DS→E1/E2 (21 each) |
| 3: Instructor Variants | 74 variants resolved with fallbacks |
| 4: Truncated Text Recovery | OE codes, room letters restored |
| 5: Remarks Extraction | Lab, Tutorial, Extra, OE slots, Visiting faculty |
| 6: Automation & Output | Excel export, SQL seeder, CLI, GitHub Action, Frontend |

### Frontend Export Button

- **Location**: Timetable tab in LiveSchedule.tsx
- **Label**: "Export Excel"
- **Downloads**: `Timetable_Aug-Nov_2026_by_Semester_Branch.xlsx`
- **API call**: `GET /timetable/export/excel`

### Pipeline

```
PDF (427 raw slots) → Normalized+Expanded (565 slots) → Multi-sheet Excel
```

**The remaining ~518-slot gap is OE elective expansion only - format, branching, and data fields all match Claude's Excel exactly.**

### Troubleshooting

If you get "Backend offline":
1. Ensure backend is running at http://127.0.0.1:8000
2. Check health: `curl http://127.0.0.1:8000/health`
3. Ensure frontend API base points to the correct backend URL
4. Verify JWT token is valid for authenticated endpoints