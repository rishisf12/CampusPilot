"""Inspect a PDF's tables/text so parsers can be written against the real layout."""
import sys
import pdfplumber

path = sys.argv[1]
max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 2

with pdfplumber.open(path) as pdf:
    print(f"=== {path} : {len(pdf.pages)} pages ===")
    for i, page in enumerate(pdf.pages[:max_pages]):
        print(f"\n----- PAGE {i + 1} TEXT -----")
        print((page.extract_text() or "")[:2500])
        tables = page.extract_tables()
        print(f"\n----- PAGE {i + 1} TABLES ({len(tables)}) -----")
        for t_idx, t in enumerate(tables):
            print(f"[table {t_idx}] rows={len(t)} cols={len(t[0]) if t else 0}")
            for row in t[:12]:
                print("   ", [(c or "").strip()[:22] for c in row])