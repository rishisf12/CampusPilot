# -*- coding: utf-8 -*-
"""Generate a Japan-targeted resume PDF matching the DOCX layout."""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, HRFlowable)

NAVY = HexColor('#1F3A5F')
SLATE = HexColor('#44546A')
GRAY = HexColor('#6B7280')
BLACK = HexColor('#212529')
LIGHT = HexColor('#F2F5F9')
RULE = HexColor('#C9D2DE')

PAGE_W, PAGE_H = A4
ML = MR = 1.9 * cm
MT = 1.6 * cm
MB = 1.4 * cm
CONTENT_W = PAGE_W - ML - MR

doc = SimpleDocTemplate(
    r'C:\Users\Appex\Documents\Default Project\CampusPilot\Rishikesh_Resume_Japan.pdf',
    pagesize=A4,
    leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB,
    title='Rishikesh Saroj - Resume', author='Rishikesh Saroj',
)

def st(name, **kw):
    base = dict(fontName='Helvetica', fontSize=9.5, leading=12.5,
                textColor=BLACK, alignment=TA_LEFT, spaceAfter=0)
    base.update(kw)
    return ParagraphStyle(name, **base)

S_NAME = st('name', fontName='Helvetica-Bold', fontSize=20, leading=24, textColor=NAVY, alignment=TA_CENTER)
S_ROLE = st('role', fontName='Helvetica-Bold', fontSize=10.5, leading=14, textColor=SLATE, alignment=TA_CENTER)
S_CONTACT = st('contact', fontSize=9, leading=12, textColor=GRAY, alignment=TA_CENTER)
S_LOC = st('loc', fontSize=9, leading=12, textColor=GRAY, alignment=TA_CENTER, fontName='Helvetica-Oblique')
S_H = st('h', fontName='Helvetica-Bold', fontSize=10.5, leading=13, textColor=NAVY, spaceBefore=8, spaceAfter=3)
S_BODY = st('body', fontSize=9.5, leading=12.6)
S_SMALL = st('small', fontSize=9, leading=11.6, textColor=SLATE)
S_SMALLG = st('smallg', fontSize=9, leading=11.6, textColor=GRAY)
S_PROJT = st('projtitle', fontName='Helvetica-Bold', fontSize=10.5, leading=13, textColor=BLACK)
S_PROJM = st('projmeta', fontSize=8.5, leading=11, textColor=GRAY, fontName='Helvetica-Oblique')
S_PROJTECH = st('projtech', fontSize=8.5, leading=11, textColor=SLATE)
S_BULLET = st('bullet', fontSize=9, leading=11.8)
S_SKILLL = st('skilll', fontSize=8.5, leading=11, textColor=NAVY, fontName='Helvetica-Bold')
S_SKILLV = st('skillv', fontSize=8.5, leading=11, textColor=SLATE)
S_FOOT = st('foot', fontSize=8, leading=10.5, textColor=GRAY, fontName='Helvetica-Oblique', alignment=TA_CENTER)

E = []

# ---- Header ----
E.append(Paragraph('RISHIKESH SAROJ', S_NAME))
E.append(Spacer(1, 1))
E.append(Paragraph('B.Tech Mechanical Engineering &middot; Software &amp; AI/ML Engineer', S_ROLE))
E.append(Spacer(1, 2))
E.append(Paragraph('+91 8299885894&nbsp;&nbsp;|&nbsp;&nbsp; rishisf120@gmail.com&nbsp;&nbsp;|&nbsp;&nbsp; github.com/rishisf12&nbsp;&nbsp;|&nbsp;&nbsp; linkedin.com/in/rishisf12', S_CONTACT))
E.append(Spacer(1, 2))
E.append(Paragraph('PDPM IIITDM Jabalpur, India&nbsp;&nbsp;&middot;&nbsp;&nbsp; Expected graduation 2028&nbsp;&nbsp;&middot;&nbsp;&nbsp; Open to relocation &mdash; seeking internship / full-time roles in Japan', S_LOC))
E.append(Spacer(1, 5))
E.append(HRFlowable(width='100%', thickness=1.2, color=NAVY, spaceAfter=6))

# ---- Professional Summary ----
E.append(Paragraph('Professional Summary', S_H))
E.append(HRFlowable(width='100%', thickness=0.8, color=NAVY, spaceAfter=4))
E.append(Paragraph(
    'Mechanical engineering undergraduate building end-to-end ML and software applications '
    '(FastAPI, PostgreSQL, React, Docker, Scikit-learn, LLMs/OCR). CampusPilot serves ~1,500 students '
    'and is expanding to mobile via React Native. Strong full-stack fundamentals with 60+ automated tests '
    'and containerized deployments.', S_BODY))
E.append(Spacer(1, 2))
E.append(Paragraph(
    '<b>Seeking a software engineering / AI-ML internship or full-time role in Japan.</b> Eager to contribute '
    'to a product-driven engineering team and grow within a Japanese company long-term.', S_BODY))
E.append(Spacer(1, 6))

# ---- Technical Skills (2-col grid) ----
E.append(Paragraph('Technical Skills', S_H))
E.append(HRFlowable(width='100%', thickness=0.8, color=NAVY, spaceAfter=5))

skills = [
    ('Languages', 'Python (primary) &middot; JavaScript/TypeScript &middot; SQL &middot; C++'),
    ('AI / ML', 'Scikit-learn &middot; OpenCV &middot; Tesseract OCR &middot; Hugging Face (Phi-3, Mistral, Gemma) &middot; Pandas &middot; NumPy &middot; Matplotlib'),
    ('Backend', 'FastAPI &middot; REST APIs &middot; SQLModel &middot; PostgreSQL &middot; Alembic &middot; Docker &middot; pytest'),
    ('Frontend / Tools', 'React &middot; Vite &middot; Tailwind CSS &middot; Recharts &middot; Git/GitHub'),
]
rows = []
for i in range(0, len(skills), 2):
    r1 = skills[i]
    r2 = skills[i+1] if i+1 < len(skills) else ('', '')
    cell1 = Table(
        [[Paragraph('<font color="#1F3A5F"><b>%s</b></font>' % r1[0], S_SKILLL),
          Paragraph(r1[1], S_SKILLV)]],
        colWidths=[CONTENT_W/2 - 6, CONTENT_W/2 - 6])
    cell2 = Table(
        [[Paragraph('<font color="#1F3A5F"><b>%s</b></font>' % r2[0], S_SKILLL),
          Paragraph(r2[1], S_SKILLV)]],
        colWidths=[CONTENT_W/2 - 6, CONTENT_W/2 - 6])
    rows.append([cell1, cell2])

skill_tbl = Table(rows, colWidths=[CONTENT_W/2, CONTENT_W/2])
skill_tbl.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,-1), LIGHT),
    ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ('LEFTPADDING', (0,0), (-1,-1), 7),
    ('RIGHTPADDING', (0,0), (-1,-1), 7),
    ('TOPPADDING', (0,0), (-1,-1), 3),
    ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ('LINEBELOW', (0,0), (-1,-1), 0, white),
]))
E.append(skill_tbl)
E.append(Spacer(1, 8))

# ---- Projects ----
E.append(Paragraph('Projects', S_H))
E.append(HRFlowable(width='100%', thickness=0.8, color=NAVY, spaceAfter=5))

def project(title, meta, tech, bullets):
    E.append(Paragraph(title, S_PROJT))
    E.append(Paragraph(meta, S_PROJM))
    E.append(Paragraph(tech, S_PROJTECH))
    E.append(Spacer(1, 2))
    for b in bullets:
        E.append(Paragraph('<bullet>&bull;</bullet>&nbsp;&nbsp;' + b, S_BULLET))
    E.append(Spacer(1, 5))

project(
    'CampusPilot &mdash; Academic management platform (~1,500 students)',
    'In progress&nbsp;&nbsp;&middot;&nbsp;&nbsp; github.com/rishisf12/CampusPilot',
    'Python &middot; FastAPI &middot; Hugging Face (LLMs) &middot; Tesseract OCR &middot; ReportLab &middot; React',
    [
        'Built an OCR + LLM pipeline that converts exam seating PDFs into JSON for roll-number lookup and generates personalized PDF timetables.',
        'Built attendance tracking with Safe/Warning/Critical flags, a “classes you can miss” calculator, and live current/next class views from PDF/CSV timetables.',
        'Designed a layered architecture (routes, services, models, OCR modules) backed by 63+ unit tests.',
    ]
)
project(
    'pocketF &mdash; Student budgeting app (solo project)',
    'In progress&nbsp;&nbsp;&middot;&nbsp;&nbsp; github.com/rishisf12',
    'Python &middot; FastAPI &middot; PostgreSQL &middot; Pandas &middot; Matplotlib &middot; Docker Compose &middot; pytest &middot; React',
    [
        'Built a CSV importer using Decimal for exact money math, flagging bad rows across 9 error types.',
        'Built burn-rate analytics and a “money runs out on” forecast with SAFE/ALERT verdicts and auto-generated charts.',
        'Containerized API + PostgreSQL with Docker Compose; tested forecast edge cases with pytest.',
    ]
)
project(
    'UrTeam &mdash; Hackathon matchmaking platform',
    'github.com/rishisf12',
    'Python &middot; FastAPI &middot; SQLModel &middot; PostgreSQL/SQLite &middot; React &middot; Vite &middot; Tailwind CSS',
    [
        'Matched students into hackathon teams via skill overlap using set-based Jaccard similarity (no ML dependencies).',
        'Designed 15+ REST endpoints (student CRUD with 409 duplicate detection, ?tech= idea filter), domain-validated emails, SQLite/PostgreSQL dual-database with auto table creation.',
        'Built a chat approval flow with owner-verified access control; 8 reusable React components with inline Tailwind CSS.',
    ]
)
project(
    'Master-DSA &mdash; DSA practice & language comparison repo',
    'github.com/rishisf12/master-dsa',
    'C++ &middot; Python &middot; Git/GitHub',
    [
        'Practicing DSA problems and tracking learning progress across topics.',
        'Comparing C++ and Python code execution, performance, and limits side by side.',
        'Maintaining a personal DSA learning log with implemented solutions and notes.',
    ]
)

# ---- Education ----
E.append(Paragraph('Education', S_H))
E.append(HRFlowable(width='100%', thickness=0.8, color=NAVY, spaceAfter=4))
E.append(Paragraph('<b>PDPM IIITDM Jabalpur, Madhya Pradesh, India</b>', S_BODY))
E.append(Paragraph('B.Tech, Mechanical Engineering&nbsp;&nbsp;&middot;&nbsp;&nbsp; Expected 2028&nbsp;&nbsp;&middot;&nbsp;&nbsp; CPI: 6.9 / 10', S_SMALL))
E.append(Paragraph('Class XII: 80%&nbsp;&nbsp;|&nbsp;&nbsp; Class X: 92%', S_SMALLG))
E.append(Spacer(1, 6))

# ---- Achievements ----
E.append(Paragraph('Achievements', S_H))
E.append(HRFlowable(width='100%', thickness=0.8, color=NAVY, spaceAfter=4))
E.append(Paragraph('<bullet>&bull;</bullet>&nbsp;&nbsp;<b>Smart India Hackathon 2026</b> &mdash; Team of 6; proposed SkyGuard AI (SIH26073), Isolation Forest + SHAP anomaly detection to separate genuine weather events from sensor faults in Automatic Weather Stations.', S_BULLET))
E.append(Spacer(1, 2))
E.append(Paragraph('<bullet>&bull;</bullet>&nbsp;&nbsp;<b>Patent</b> &mdash; Co-inventor, Indian Patent Application No. 202621096766 A: adjustable hybrid welding device with integrated safety measures.', S_BULLET))
E.append(Spacer(1, 2))
E.append(Paragraph('<bullet>&bull;</bullet>&nbsp;&nbsp;<b>Jagrati (Volunteer)</b> &mdash; Teach underprivileged village children weekly; help plan the student-run initiative’s activities.', S_BULLET))
E.append(Spacer(1, 10))

# ---- Footer rule + note ----
E.append(HRFlowable(width='100%', thickness=0.7, color=RULE, spaceAfter=3))
E.append(Paragraph('References available upon request.&nbsp;&nbsp;&middot;&nbsp;&nbsp; Portfolio &amp; code: github.com/rishisf12', S_FOOT))

doc.build(E)
print('PDF built.')
